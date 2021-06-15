import datajoint as dj
import numpy as np
# import pynwb
# import re
import warnings

from ..common.common_spikesorting import SortGroup, SortInterval, CuratedSpikeSorting, SpikeSorting, UnitInclusionParameters
from ..common.common_device import Probe  # noqa: F401
from ..common.common_filter import FirFilter
from ..common.common_interval import IntervalList    # noqa: F401
# SortInterval, interval_list_intersect, interval_list_excludes_ind
from ..common.common_nwbfile import Nwbfile, AnalysisNwbfile
from ..common.common_region import BrainRegion  # noqa: F401
from ..common.common_session import Session  # noqa: F401
from ..common.nwb_helper_fn import (get_valid_intervals, estimate_sampling_rate, get_electrode_indices, get_data_interface,
                            get_nwb_file)
from ..common.dj_helper_fn import fetch_nwb 

schema = dj.schema('decoding_clusterless')

@schema
class MarkParameters(dj.Manual):
    definition = """
    mark_param_name : varchar(80) # a name for this set of parameters
    ---
    mark_param_dict:    BLOB    # dictionary of parameters for the mark extraction function
    """

    def insert_default_param(self):
        """insert the default parameter set {'amplitude': 1}
        """
        default_dict = {'amplitude' : 1}
        self.insert1({'mark_parameter_list_name' : 'default',
                       'mark_parmeter_dict' : default_dict})

@schema
class UnitMarkParameters(dj.Manual):
    definition = """
    -> CuratedSpikeSorting
    -> UnitInclusion
    -> MarkParameters
    """

@schema
class UnitMarks(dj.Computed):
    definition="""
    -> UnitMarkParameters
    ---
    -> AnalysisNwbfile
    unit_marks_object_id: varchar(40) # the NWB object that stores the marks
    """
    def make(self, key):
        # get the list of mark parameters
        mark_param_dict = (MarkParameters & key['mark_param_name']).fetch1('mark_param_dict')
        # get the list of units
        