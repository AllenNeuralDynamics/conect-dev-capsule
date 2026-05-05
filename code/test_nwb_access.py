import sys

sys.path.insert(0, "code")

import nwb_access


def test_trial_column_descriptions():
    descriptions = nwb_access.get_table_column_descriptions(
        "/intervals/trials",
        session_id="713655_2024-08-09",
        columns=("stim_name", "response_time", "is_instruction"),
    )

    assert set(descriptions) == {"stim_name", "response_time", "is_instruction"}
    assert "stimulus" in descriptions["stim_name"].lower()
    assert "response" in descriptions["response_time"].lower()
    assert "inform the subject" in descriptions["is_instruction"].lower()


if __name__ == "__main__":
    test_trial_column_descriptions()
    print("nwb_access helper tests passed")
