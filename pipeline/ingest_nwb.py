import logging
import os.path
import pathlib
import sys

from franklab_nwb_extensions import fl_extension  # noqa
from pynwb import NWBHDF5IO
from tqdm import tqdm

import datajoint as dj
from pipeline import experiment

IGNORED_LFP_FIELDS = ['electrodes', 'data', 'timestamps']


def run_ingest(nwb_dir):
    logging.info(dj.config)
    file_paths = pathlib.Path(nwb_dir).joinpath().glob("*.nwb")
    for file_path in file_paths:
        absolute_path = str(file_path.absolute())
        with NWBHDF5IO(absolute_path, 'r', load_namespaces=True) as io:
            nwbfile = io.read()

            # Experimenter Info
            experiment.Lab.insert1(
                (nwbfile.lab, nwbfile.institution), skip_duplicates=True)
            experiment.Experimenter.insert1(
                (nwbfile.experimenter), skip_duplicates=True)

            # Subject Info
            subj = nwbfile.subject.fields
            # rename description to subject description to maintain uniqueness
            subj['subject_description'] = subj.pop('description')
            subj.pop('weight')  # ignore weight
            experiment.Subject.insert1(subj, skip_duplicates=True)

            # Session Info
            nwb_filename = os.path.basename(absolute_path)
            experiment.Session.insert1(
                (nwbfile.subject.subject_id,
                 nwbfile.session_id,
                 nwbfile.experimenter,
                 nwbfile.experiment_description,
                 nwb_filename), skip_duplicates=True)

            # Probe Info
            probe_insertions = [
                dict(subject_id=nwbfile.subject.subject_id,
                     session_id=nwbfile.session_id,
                     insertion_number=int(series['group_name']))
                for _, series
                in nwbfile.ec_electrodes.to_dataframe().iterrows()]

            experiment.ProbeInsertion.insert(
                probe_insertions, skip_duplicates=True)

            # LFP Info
            lfp_dict = nwbfile.acquisition['LFP']['electrical_series'].fields

            lfp_entry = {
                f'lfp_{key_name}': value for key_name, value in lfp_dict.items()
                if key_name not in IGNORED_LFP_FIELDS}
            lfp_entry['lfp_oid'] = (
                nwbfile.acquisition['LFP']['electrical_series'].object_id)

            for probe_insertion in tqdm(
                    experiment.ProbeInsertion.fetch('KEY'), desc='LFP Info'):
                experiment.LFP.insert1(dict(**lfp_entry, **probe_insertion),
                                       allow_direct_insert=True,
                                       skip_duplicates=True)


if __name__ == "__main__":
    sys.exit(run_ingest(sys.argv[1]))
