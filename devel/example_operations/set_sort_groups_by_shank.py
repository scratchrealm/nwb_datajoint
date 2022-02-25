#!/usr/bin/env python3

import nwb_datajoint.common as ndc

nwb_file_name = 'RN2_20191110_.nwb'

ndc.SortGroup().set_group_by_shank(
    nwb_file_name=nwb_file_name,
    references=None,
    omit_ref_electrode_group=False
)

print(ndc.SortGroup & {'nwb_file_name': nwb_file_name})
print(ndc.SortGroup.SortGroupElectrode & {'nwb_file_name': nwb_file_name})