import datajoint as dj

from .common_device import CameraDevice, DataAcquisitionDevice, Probe
from .common_lab import Institution, Lab, LabMember
from .common_nwbfile import Nwbfile
from .common_subject import Subject
from .nwb_helper_fn import get_nwb_file

schema = dj.schema('common_session')

# TODO: figure out what to do about ExperimenterList


@schema
class Session(dj.Imported):
    definition = """
    # Table for holding experimental sessions.
    -> Nwbfile
    ---
    -> [nullable] Subject
    -> [nullable] Institution
    -> [nullable] Lab
    session_id = NULL: varchar(200)
    session_description: varchar(2000)
    session_start_time: datetime
    timestamps_reference_time: datetime
    experiment_description = NULL: varchar(2000)
    """

    def make(self, key):
        # These imports must go here to avoid cyclic dependencies
        # from .common_task import Task, TaskEpoch
        from .common_interval import IntervalList
        # from .common_ephys import Unit

        nwb_file_name = key['nwb_file_name']
        nwb_file_abspath = Nwbfile.get_abs_path(nwb_file_name)
        nwbf = get_nwb_file(nwb_file_abspath)

        # certain data are not associated with a single NWB file / session because they may apply to
        # multiple sessions. these data go into dj.Manual tables
        # e.g., a lab member may be associated with multiple experiments, so the lab member table should not
        # be dependent on (contain a primary key for) a session

        print('Institution...')
        Institution().insert_from_nwbfile(nwbf)

        print('Lab...')
        Lab().insert_from_nwbfile(nwbf)

        print('LabMember...')
        LabMember().insert_from_nwbfile(nwbf)

        print('Subject...')
        Subject().insert_from_nwbfile(nwbf)

        print('DataAcquisitionDevice...')
        DataAcquisitionDevice().insert_from_nwbfile(nwbf)

        print('CameraDevice...')
        CameraDevice().insert_from_nwbfile(nwbf)

        print('Probe...')
        Probe().insert_from_nwbfile(nwbf)

        if nwbf.subject is not None:
            subject_id = nwbf.subject.subject_id
        else:
            subject_id = None

        Session().insert1({
            'nwb_file_name': nwb_file_name,
            'subject_id': subject_id,
            'institution_name': nwbf.institution,
            'lab_name': nwbf.lab,
            'session_id': nwbf.session_id,
            'session_description': nwbf.session_description,
            'session_start_time': nwbf.session_start_time,
            'timestamps_reference_time': nwbf.timestamps_reference_time,
            'experiment_description': nwbf.experiment_description
        }, skip_duplicates=True)

        print('Skipping Apparatus for now...')
        # Apparatus().insert_from_nwbfile(nwbf)

        # interval lists depend on Session (as a primary key) but users may want to add these manually so this is
        # a manual table that is also populated from NWB files

        print('IntervalList...')
        IntervalList().insert_from_nwbfile(nwbf, nwb_file_name=nwb_file_name)

        # print('Unit...')
        # Unit().insert_from_nwbfile(nwbf, nwb_file_name=nwb_file_name)

@schema
class ExperimenterList(dj.Imported):
    definition = """
    -> Session
    """

    class Experimenter(dj.Part):
        definition = """
        -> ExperimenterList
        -> LabMember
        """

    def make(self, key):
        nwb_file_name = key['nwb_file_name']
        nwb_file_abspath = Nwbfile().get_abs_path(nwb_file_name)
        self.insert1({'nwb_file_name': nwb_file_name}, skip_duplicates=True)  # TODO is this necessary??
        nwbf = get_nwb_file(nwb_file_abspath)

        if nwbf.experimenter is None:
            return

        for name in nwbf.experimenter:
            LabMember().insert_from_name(name)
            key = dict()
            key['nwb_file_name'] = nwb_file_name
            key['lab_member_name'] = name
            self.Experimenter().insert1(key)

@schema
class SessionGroup(dj.Manual):
    definition = """
    session_group_name: varchar(200)
    ---
    session_group_description: varchar(2000)
    """
    @staticmethod
    def add_group(session_group_name: str, session_group_description):
        SessionGroup.insert1({
            'session_group_name': session_group_name,
            'session_group_description': session_group_description
        })
    @staticmethod
    def update_session_group_description(session_group_name: str, session_group_description):
        SessionGroup.update1({
            'session_group_name': session_group_name,
            'session_group_description': session_group_description
        })
    @staticmethod
    def add_session_to_group(nwb_file_name: str, session_group_name: str):
        SessionGroupSession.insert1({
            'session_group_name': session_group_name,
            'nwb_file_name': nwb_file_name
        })
    @staticmethod
    def remove_session_from_group(nwb_file_name: str, session_group_name: str):
        query = {'session_group_name': session_group_name, 'nwb_file_name': nwb_file_name}
        (SessionGroupSession & query).delete()
    @staticmethod
    def delete_group(session_group_name: str):
        query = {'session_group_name': session_group_name}
        (SessionGroup & query).delete()
    @staticmethod
    def get_group_sessions(session_group_name: str):
        results = (SessionGroupSession & {'session_group_name': session_group_name}).fetch(as_dict=True)
        return [
            {'nwb_file_name': result['nwb_file_name']}
            for result in results
        ]

# The reason this is not implemented as a dj.Part is that
# datajoint prohibits deleting from a subtable without
# also deleting the parent table.
# See: https://docs.datajoint.org/python/computation/03-master-part.html
@schema
class SessionGroupSession(dj.Manual):
    definition = """
    -> SessionGroup
    -> Session
    """