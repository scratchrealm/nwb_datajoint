import datajoint as dj
import sortingview as sv
import numpy as np
import pandas as pd
import pynwb

from ..common.common_nwbfile import AnalysisNwbfile
from ..common.common_spikesorting import (CuratedSpikeSorting, SpikeSortingWorkspace,
                                          UnitInclusionParameters)
from ..common.dj_helper_fn import fetch_nwb  # dj_replace
from .get_unit_waveforms import get_unit_waveforms

schema = dj.schema('decoding_clusterless')


@schema
class MarkParameters(dj.Manual):
    definition = """
    mark_param_name : varchar(80) # a name for this set of parameters
    ---
    mark_type = 'amplitude':  varchar(40) # the type of mark. Currently only 'amplitude' is supported
    mark_param_dict:    BLOB    # dictionary of parameters for the mark extraction function
    """

    def insert_default_param(self):
        """insert the default parameter set {'sign': -1, 'threshold' : 100} corresponding to negative going waveforms of at least 100 uV size
        """
        default_dict = {'sign': -1, 'threshold': 100}
        self.insert1({'mark_param_name': 'default',
                      'mark_param_dict': default_dict}, skip_duplicates=True)

    @staticmethod
    def supported_mark_type(mark_type):
        """checks whether the requested mark type is supported. Currently only 'amplitude" is supported

        Args:
            mark_type (str): the requested mark type
        """
        supported_types = ['amplitude']
        if mark_type in supported_types:
            return True
        return False


@schema
class UnitMarkParameters(dj.Manual):
    definition = """
    -> CuratedSpikeSorting
    -> UnitInclusionParameters
    -> MarkParameters
    """


@schema
class UnitMarks(dj.Computed):
    definition = """
    -> UnitMarkParameters
    ---
    -> AnalysisNwbfile
    marks_object_id: varchar(40) # the NWB object that stores the marks
    """

    def make(self, key):
        # get the list of mark parameters
        mark_param = (MarkParameters & key).fetch1()
        mark_param_dict = mark_param['mark_param_dict']

        # check that the mark type is supported
        if not MarkParameters().supported_mark_type(mark_param['mark_type']):
            Warning(
                f'Mark type {mark_param["mark_type"]} not supported; skipping')
            return

        # get the list of units
        units = UnitInclusionParameters().get_included_units(key, key)

        # retrieve the units from the NWB file
        nwb_units = (CuratedSpikeSorting() & key).fetch_nwb()[0]['units']
    
        # get the  workspace so we can get the waveforms from the recording
        workspace_uri = (SpikeSortingWorkspace & key).fetch1('workspace_uri')
        sorting_id = (CuratedSpikeSorting & key).fetch1('sorting_id')
        workspace = sv.load_workspace(workspace_uri)
        recording = workspace.get_recording_extractor(
            workspace.recording_ids[0])
        sorting = workspace.get_sorting_extractor(sorting_id)
        channel_ids = recording.get_channel_ids()
        # assume the channels are all the same for the moment. This would need to be changed for larger probes
        channel_ids_by_unit = [channel_ids] * (max(units['unit_id']) + 1)
        # here we only get 8 points because that should be plenty to find the minimum/maximum
        waveforms = get_unit_waveforms(
            recording, sorting, units['unit_id'], channel_ids_by_unit, 8)

        if mark_param['mark_type'] == 'amplitude':
            # get the marks and timestamps
            #marks = np.empty((0, 4), dtype='int16')
            # more flexible if there are dead channels
            marks = np.empty((0, waveforms[0][0].shape[0]), dtype='int16')
            timestamps = np.empty((0), dtype='float64')
            for index, unit in enumerate(waveforms):
                marks = np.concatenate(
                    (marks, np.amin(np.asarray(unit, dtype='int16'), axis=2)), axis=0)
                timestamps = np.concatenate(
                    (timestamps, nwb_units.loc[units['unit_id'][index]].spike_times), axis=0)
            # sort the timestamps to order them properly
            sort_order = np.argsort(timestamps)
            timestamps = timestamps[sort_order]
            marks = marks[sort_order, :]

            if 'threshold' in mark_param_dict:
                print('thresholding')
                # filter the marks by the amplitude threshold
                if mark_param_dict['sign'] == -1:
                    include = np.where(
                        np.amax(marks, axis=1) <= (mark_param_dict['sign'] *
                                                   mark_param_dict['threshold'])
                    )[0]
                elif mark_param_dict['sign'] == -1:
                    include = np.where(np.amax(marks, axis=1)
                                       >= mark_param_dict['threshold'])[0]
                else:
                    include = np.where(
                        np.abs(np.amax(marks, axis=1)) >= mark_param_dict['threshold'])[0]
                timestamps = timestamps[include]
                marks = marks[include, :]

            # create a new AnalysisNwbfile and a timeseries for the marks and save
            key['analysis_file_name'] = AnalysisNwbfile().create(
                key['nwb_file_name'])
            nwb_object = pynwb.TimeSeries(
                name='marks',
                data=marks,
                unit='uV',
                timestamps=timestamps,
                description=f'amplitudes of spikes from electrodes {recording.get_channel_ids()}')
            key['marks_object_id'] = (AnalysisNwbfile().add_nwb_object(
                key['analysis_file_name'], nwb_object))
            AnalysisNwbfile().add(key['nwb_file_name'],
                                  key['analysis_file_name'])
            self.insert1(key)

    def fetch_nwb(self, *attrs, **kwargs):
        return fetch_nwb(self, (AnalysisNwbfile, 'analysis_file_abs_path'), *attrs, **kwargs)

    def fetch1_dataframe(self):
        return self.fetch_dataframe()[0]

    def fetch_dataframe(self):
        return [self._convert_to_dataframe(data) for data in self.fetch_nwb()]

    @staticmethod
    def _convert_to_dataframe(nwb_data):
        n_marks = nwb_data['marks'].data.shape[1]
        columns = [f'amplitude_{ind}' for ind in range(n_marks)]
        return pd.DataFrame(nwb_data['marks'].data,
                            index=pd.Index(nwb_data['marks'].timestamps,
                                           name='time'),
                            columns=columns)
