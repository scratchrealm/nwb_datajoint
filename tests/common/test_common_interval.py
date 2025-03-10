import numpy as np
from nwb_datajoint.common.common_interval import interval_list_intersect

def test_interval_list_intersect():
    interval_list1 = np.array([
        [0,10],[3,5],[14,16]
    ])
    interval_list2 = np.array([
        [10,11],[9,14],[13,18]
    ])
    intersection_list = interval_list_intersect(interval_list1, interval_list2)
    assert np.all(intersection_list==np.array([[9,10],[14,16]]))
