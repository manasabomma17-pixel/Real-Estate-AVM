"""Checks the quarterly price updates and the sale reports users send."""

import pytest

from backend.services import auth, market_index
from data_processing.update_price_index import add_quarter


@pytest.fixture
def index_file(tmp_path):
    path = tmp_path / "index.csv"
    path.write_text("quarter,change_percent,source,released\n")
    return path


def test_no_updates_means_no_change(index_file):
    updates = market_index.load_updates(index_file)
    assert updates == []
    assert market_index.multiplier(updates) == 1.0
    assert market_index.updated_to(updates) == "October 2026"


def test_quarters_multiply(index_file):
    add_quarter("Oct-Dec 2026", 2.0, "NHB RESIDEX", "2027-03-15", index_file)
    total = add_quarter("Jan-Mar 2027", 3.0, "NHB RESIDEX", "2027-06-15", index_file)
    assert total == pytest.approx(1.02 * 1.03)
    assert market_index.updated_to(market_index.load_updates(index_file)) == "Jan-Mar 2027"


def test_bad_quarters_are_refused(index_file):
    add_quarter("Oct-Dec 2026", 2.0, "NHB RESIDEX", "", index_file)
    with pytest.raises(ValueError):
        add_quarter("Oct-Dec 2026", 1.0, "NHB RESIDEX", "", index_file)   # already there
    with pytest.raises(ValueError):
        add_quarter("Jan-Mar 2027", 45, "NHB RESIDEX", "", index_file)    # a typo, surely
    with pytest.raises(ValueError):
        add_quarter("Jan-Mar 2027", 1.0, " ", "", index_file)             # no source


def test_the_real_file_starts_at_october_2026():
    # the locality rates already cover prices up to October 2026
    assert market_index.MULTIPLIER >= 1.0
    assert isinstance(market_index.UPDATED_TO, str)


def test_sale_reports_are_saved_and_limited(tmp_path):
    store = auth.UserStore("sqlite:///" + str(tmp_path / "users.db"))
    for i in range(auth.REPORTS_PER_DAY):
        store.add_report("1", "Whitefield", 1200, 2, 2, 150 + i, "bought", 156.6, now=1000 + i)
    with pytest.raises(auth.AuthError) as too_many:
        store.add_report("1", "Whitefield", 1200, 2, 2, 150, "bought", 156.6, now=2000)
    assert too_many.value.status == 429
    store.add_report("2", "Whitefield", 1200, 2, 2, 160, "sold", 156.6, now=2000)  # another user is fine
    rows = store.reports()
    assert len(rows) == auth.REPORTS_PER_DAY + 1
    assert rows[0]["location"] == "Whitefield" and rows[-1]["kind"] == "sold"
