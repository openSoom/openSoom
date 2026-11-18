import json

import pytest
from fastapi import HTTPException

from opensoom.technician import FieldDesk


class Stream:
    def __init__(self):
        self.parent = "cnt1"
        self.rows = ["one"]
        self.tag = 1
        self.disabled = False
        self.omit_last = False
        self.append_during_read = False

    def retrieve(self, path, params=None):
        cnt = {"ri": self.parent, "st": self.tag, "cni": len(self.rows), "disr": self.disabled}
        if params:
            assert params.get("sts", 1) > 0  # ACME rejects zero as a state-tag filter.
            ids = self.rows
            if self.omit_last:
                ids = ids[:-1]
            start = params.get("sts", 0)
            offset = params.get("ofst", 1) - 1
            ids = ids[offset:offset + params.get("lim", len(ids))]
            children = []
            for name in ids:
                tag = self.rows.index(name) + 1
                if tag > start:
                    children.append({"ri":name, "pi":self.parent, "st":tag, "ct":"20261119T004400",
                                     "con":json.dumps({"facility_id":"site", "value":name})})
            cnt["m2m:cin"] = children
            if self.append_during_read:
                self.rows.append("arrived-while-listing")
                self.tag += 1
                self.append_during_read = False
        return {"body":{"m2m:cnt":cnt},"rqi":"test-read"}


def desk_for(cse):
    return FieldDesk({"facility_id":"site","facility_path":"mn/opensoom/facilities/site","name":"Site",
                      "profile":"test","simulation":True,"zones":{}}, cse)


def test_torn_paginated_snapshot_is_retried_and_incomplete_reads_are_not_cached():
    cse = Stream()
    desk = desk_for(cse)
    desk.PAGE_SIZE = 1
    cse.append_during_read = True
    assert [r["value"] for r in desk.stream("work_orders")] == ["one","arrived-while-listing"]
    cse.tag += 1
    cse.rows.append("new")
    cse.omit_last = True
    with pytest.raises(HTTPException) as failed:
        desk.stream("work_orders")
    assert failed.value.status_code == 503
    cse.omit_last = False
    assert [r["value"] for r in desk.stream("work_orders")] == ["one","arrived-while-listing","new"]


def test_cache_checks_container_identity_membership_and_retrieval_permission():
    cse = Stream()
    desk = desk_for(cse)
    assert desk.stream("inspection_notes")[0]["value"] == "one"
    cse.parent = "replacement"
    cse.rows = ["replacement-note"]
    assert desk.stream("inspection_notes")[0]["value"] == "replacement-note"
    cse.disabled = True
    with pytest.raises(HTTPException) as denied:
        desk.stream("inspection_notes")
    assert denied.value.status_code == 503
    cse.disabled = False
    cse.rows.clear()
    assert desk.stream("inspection_notes") == []


def test_first_append_to_an_empty_new_stream_uses_a_supported_read():
    cse = Stream()
    cse.rows = []
    cse.tag = 0
    desk = desk_for(cse)
    assert desk.stream("inspection_notes") == []
    cse.rows.append("first")
    cse.tag = 1
    assert desk.stream("inspection_notes")[0]["resource_id"] == "first"
