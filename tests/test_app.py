"""
test_app.py -- end-to-end checks of the web app, using Streamlit's AppTest.

    python3 -m unittest discover tests

Needs only the committed output/ files (no data_real/).
"""

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
import readiness_checker as rc  # noqa: E402
from validate_croissant import validate  # noqa: E402

# Runs app.py's code up to its navigation, then one page function. HOOK runs after the page.
RUNNER = """
import io
from pathlib import Path
import streamlit as st
__file__ = {app!r}
exec(compile(Path(__file__).read_text().split("st.set_page_config(")[0], __file__, "exec"))
{setup}
{page}()
{hook}
"""
# Builds the exports with the same functions as the download buttons, and records the review.
EXPORT_HOOK = """
ss = st.session_state
data_, catalog_ = load_projects(), field_catalog()
levels_ = count_levels(ss["needs"], catalog_)
level_ = ss["level"] if ss.get("level") in levels_ else levels_[0]
reviewed_ = basket_review(data_, ss["needs"], level_, catalog_, ss.get("min_records", 100), ss.get("species"))
ss["_review"] = [(r["project"]["key"], r["status"], r["met"], r["total"]) for r in reviewed_]
if reviewed_:
    totals_ = basket_totals(reviewed_, level_, ss["needs"], ss.get("species"))
    ss["_croissant"] = basket_croissant(reviewed_, data_, ss["needs"], catalog_)
    ss["_manifest"] = manifest_rows(reviewed_, data_, ss["needs"], catalog_, ss.get("min_records", 100))
    ss["_report"] = basket_report(reviewed_, data_, ss["needs"], catalog_, totals_, ss.get("min_records", 100))
"""
COMPARISON = json.load(open(ROOT / "output" / "readiness_comparison.json"))
PROJECTS = json.load(open(ROOT / "output" / "readiness_projects.json"))
ORDER = {p["program"]: p["field_order"] for p in PROJECTS["programs"]}
BY_KEY = {f"{p['program']}|{p['id'][0]}|{p['id'][1]}": p for p in PROJECTS["projects"]}
STEPS = ["1. Choose", "2. Needs", "3. Review", "4. Export"]


def app(page: str, setup: str = "", hook: str = "") -> AppTest:
    code = RUNNER.format(app=str(ROOT / "app.py"), page=page, setup=setup, hook=hook)
    return AppTest.from_string(code, default_timeout=180)


def expected_status(project: dict, level: str, chosen: list[str], minimum: int, species: str | None = None) -> tuple:
    """The status worked out directly from the stored bitmasks, not with the app's code."""
    order = ORDER[project["program"]]
    patterns = project["combinations"][level]["patterns"]
    total = project["combinations"][level]["total"]
    if species:
        bit = 1 << order.index({"human": "_human", "animal": "_animal"}[species])
        patterns = [[m, n] for m, n in patterns if m & bit]
        total = sum(n for _, n in patterns)
    met = 0
    if all(c in order for c in chosen):
        mask = sum(1 << order.index(c) for c in chosen)
        met = sum(n for m, n in patterns if m & mask == mask)
    if level == "subject" and {"sex", "age"} & set(chosen):
        total = sum(n for m, n in patterns if m & (1 << order.index("_single_organism")))
    status = ("Meets your needs" if met >= minimum else "Doesn't meet your needs" if met == 0
              else "Complete but small" if met == total else "Partly")
    return status, met, total


class AppCase(unittest.TestCase):
    def assertClean(self, at: AppTest):
        self.assertEqual([e.value for e in at.exception], [])
        self.assertEqual([e.value for e in at.error], [])


class RealNavigation(AppCase):
    def test_runs_through_app_py(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
        self.assertClean(at)
        self.assertEqual(at.title[0].value, "CFDE metadata AI-readiness at a glance")

    def test_sidebar_shows_the_basket_once_it_has_projects(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        at.session_state["basket"] = list(BY_KEY)[:2]
        at.run()
        self.assertClean(at)
        labels = [e.proto.label for e in at.sidebar.get("page_link")]
        self.assertIn("Basket: 2 projects", labels)


class Pages(AppCase):
    def test_every_page_renders(self):
        for page in ("overview", "field_coverage_page", "finder_page", "program_page", "basket_page", "methods_page",
                     "upload_page"):
            with self.subTest(page=page):
                self.assertClean(app(page).run())

    def test_overview_cards_and_paths(self):
        at = app("overview").run()
        cards = next(m.value for m in at.markdown if "cfde-cards" in m.value)
        self.assertEqual(cards.count('class="cfde-card"'), len(COMPARISON["programs"]))
        self.assertIn("Older release", cards)
        self.assertEqual(len(at.get("page_link")), 4)  # 3 starting points + "Sex and age by species"

    def test_report_card_for_every_program(self):
        at = app("program_page").run()
        for program in at.selectbox[0].options:
            with self.subTest(program=program):
                at.selectbox[0].set_value(program).run()
                self.assertClean(at)

    def test_full_checks_do_not_repeat_themselves(self):
        at = app("program_page").run()
        self.assertFalse([c.value for c in at.caption if "have it recorded." in c.value])

    def test_methods_has_tabs_and_the_named_rule(self):
        at = app("methods_page").run()
        self.assertEqual(len(at.tabs), 6)
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("AGE_ZERO_PLACEHOLDER", text)
        self.assertIn("Complete but small", text)


class Finder(AppCase):
    def tick(self, at, wanted):
        for cb in at.checkbox:
            if cb.key and cb.key.startswith("finder_need_"):
                cb.set_value(cb.key.removeprefix("finder_need_") in wanted)
        return at.run()

    def lines(self, at):
        return [m.value for m in at.markdown if m.value.startswith("- **")]

    def test_verified_counts_and_the_answer_first(self):
        at = app("finder_page").run()
        self.assertClean(at)
        lines = self.lines(at)
        self.assertIn("- **ExRNA:** 7,072 of 8,580 single-organism subjects have age and sex", lines)
        self.assertIn("- **SenNet:** 450 of 897 single-organism subjects have age and sex", lines)
        self.assertIn("- **LINCS:** 0 of 275 single-organism subjects have age and sex (fewer than 100)", lines)
        headings = [m.value for m in at.markdown if m.value.startswith("####")]
        self.assertEqual(headings[0], "#### 3 of 7 programs have at least 100 single-organism subjects with age and sex")

    def test_sex_rule_and_minimum_note_are_on_the_page(self):
        at = app("finder_page").run()
        captions = " ".join(c.value for c in at.caption)
        self.assertIn("Sex = male or female recorded; Indeterminate not counted", captions)
        self.assertIn("There's no universal minimum for training AI", captions)

    def test_nothing_selected_gives_guidance(self):
        at = self.tick(app("finder_page").run(), [])
        self.assertClean(at)
        self.assertIn("Select at least one field", at.info[0].value)

    def test_starting_points(self):
        at = app("finder_page").run()
        at.button(key="finder_preset_Files ready to load").click().run()
        self.assertClean(at)
        self.assertEqual(at.session_state["needs"], ["checksum", "file.file_format"])
        self.assertEqual({c.key for c in at.checkbox if c.value},
                         {"finder_need_checksum", "finder_need_file.file_format"})
        at.button(key="finder_preset_clear").click().run()
        self.assertEqual(at.session_state["needs"], [])

    def test_field_combinations_at_each_level(self):
        at = app("finder_page").run()
        for combo in (["sex"], ["biosample.anatomy", "disease"], ["subject_race.race", "subject.ethnicity"],
                      ["biosample.biofluid", "file.assay_type"], ["persistent_id"]):
            at = self.tick(at, combo)
            levels = next((r.options for r in at.radio if r.key == "finder_level"), [None])
            for level in levels:
                if level:
                    at.radio(key="finder_level").set_value(level).run()
                with self.subTest(combo=combo, level=level):
                    self.assertClean(at)
                    self.assertTrue(self.lines(at))


class Basket(AppCase):
    def start(self, basket=None, needs=None, minimum=None, step=None):
        at = app("basket_page", hook=EXPORT_HOOK)
        if basket is not None:
            at.session_state["basket"] = basket
        if needs is not None:
            at.session_state["needs"] = needs
        if minimum is not None:
            at.session_state["min_records"] = minimum
        if step is not None:
            at.session_state["basket_step"] = step
        return at.run()

    def test_add_through_search_then_step_through(self):
        at = self.start()
        self.assertClean(at)
        at.text_input(key="basket_search").set_value("kidney").run()
        shown = at.session_state["basket_shown"]
        self.assertTrue(shown)
        at.button(key="basket_add_all").click().run()
        self.assertEqual(sorted(at.session_state["basket"]), sorted(shown))
        for step in STEPS[1:]:
            at.button(key="basket_next").click().run()
            self.assertClean(at)
            self.assertEqual(at.session_state["basket_step"], step)
        self.assertEqual(len(at.get("download_button")), 4)
        at.button(key="basket_back").click().run()
        self.assertEqual(at.session_state["basket_step"], STEPS[2])

    def test_search_and_filters_survive_changing_steps(self):
        at = self.start()
        at.text_input(key="basket_search").set_value("kidney").run()
        at.button(key="basket_next").click().run()
        at.button(key="basket_back").click().run()
        self.assertEqual(at.text_input(key="basket_search").value, "kidney")

    def test_empty_states_offer_the_way_forward(self):
        at = self.start(step=STEPS[2])
        self.assertClean(at)
        self.assertIn("basket is empty", at.info[0].value)
        at.button(key="basket_goto_choose").click().run()
        self.assertEqual(at.session_state["basket_step"], STEPS[0])

        at = self.start(basket=list(BY_KEY)[:1], needs=[], step=STEPS[3])
        self.assertIn("at least one need", at.info[0].value)
        at.button(key="basket_goto_needs").click().run()
        self.assertEqual(at.session_state["basket_step"], STEPS[1])

    def test_no_matches_gives_guidance(self):
        at = self.start()
        at.text_input(key="basket_search").set_value("zzzz-no-such-project").run()
        self.assertClean(at)
        self.assertIn("No projects match", at.info[0].value)

    def test_needs_are_shared_and_survive_the_step_change(self):
        at = self.start(step=STEPS[1])
        at.checkbox(key="basket_need_biosample.anatomy").set_value(True).run()
        at.button(key="basket_next").click().run()
        at.button(key="basket_back").click().run()
        self.assertTrue(at.checkbox(key="basket_need_biosample.anatomy").value)
        self.assertIn("biosample.anatomy", at.session_state["needs"])

    def test_statuses_match_an_independent_count(self):
        keys = [k for k, p in BY_KEY.items() if p["program"] in ("Kids First", "ExRNA", "SenNet")]
        for minimum in (1, 100, 1000):
            with self.subTest(minimum=minimum):
                at = self.start(basket=keys, needs=["sex", "age"], minimum=minimum, step=STEPS[2])
                self.assertClean(at)
                for key, status, met, total in at.session_state["_review"]:
                    self.assertEqual((status, met, total), expected_status(BY_KEY[key], "subject", ["sex", "age"], minimum))

    def test_remove_keeps_complete_but_small(self):
        keys = [k for k, p in BY_KEY.items()
                if p["program"] in ("Kids First", "ExRNA", "SenNet") and p["parent"] and not p["sub_projects"]]
        at = self.start(basket=keys, needs=["sex", "age"], minimum=300, step=STEPS[2])
        before = at.session_state["_review"]
        small = {k for k, s, _, _ in before if s == "Complete but small"}
        none = {k for k, s, _, _ in before if s == "Doesn't meet your needs"}
        self.assertTrue(small and none)
        at.button(key="basket_remove_not_met").click().run()
        left = set(at.session_state["basket"])
        self.assertTrue(small <= left)
        self.assertFalse(none & left)

    def test_summary_explains_the_qualifying_number(self):
        keys = [k for k, p in BY_KEY.items()
                if p["program"] in ("Kids First", "ExRNA", "SenNet") and p["parent"] and not p["sub_projects"]]
        at = self.start(basket=keys, needs=["sex", "age"], minimum=300, step=STEPS[2])
        review = at.session_state["_review"]
        total = sum(m for _, _, m, _ in review)
        meeting = sum(m for _, s, m, _ in review if s == "Meets your needs")
        expected = f"{total:,} qualifying single-organism subjects ({meeting:,} in projects that meet your needs)"
        self.assertIn(expected, [c.value for c in at.caption])

    def test_exports(self):
        keys = [k for k, p in BY_KEY.items() if p["program"] in ("Metabolomics Workbench",)][:5] + \
               [k for k, p in BY_KEY.items() if p["program"] in ("ExRNA", "Kids First")][:9]
        at = self.start(basket=keys, needs=["sex", "age", "subject_race.race"], step=STEPS[3])
        self.assertClean(at)
        self.assertEqual(validate(at.session_state["_croissant"]), [])
        self.assertTrue(any(r["@id"].endswith("subject_race") for r in at.session_state["_croissant"]["recordSet"]))
        self.assertEqual(len(at.session_state["_manifest"]), len(keys))
        self.assertIn("# Dataset basket summary", at.session_state["_report"])


class Upload(AppCase):
    def test_a_small_real_shaped_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(path, "w") as z:
                for tsv in (ROOT / "data").glob("*.tsv"):
                    z.write(tsv, tsv.name)
            setup = f"""
class Upload(io.BytesIO):
    name = "sample.zip"
    size = Path({str(path)!r}).stat().st_size
st.file_uploader = lambda *a, **k: Upload(Path({str(path)!r}).read_bytes())
"""
            at = app("upload_page", setup=setup).run()
            self.assertClean(at)
            self.assertTrue(at.success)
            self.assertEqual(len(at.get("page_link")), 1)


class Species(AppCase):
    def program(self, label):
        return next(p for p in COMPARISON["programs"] if p["program"] == label)

    def test_species_split_matches_the_raw_data(self):
        # Checked by hand against subject.tsv and subject_role_taxonomy.tsv.
        self.assertEqual(self.program("LINCS")["species"], {"human": {"subjects": 275, "sex": 0, "age": 0}})
        sparc = self.program("SPARC")["species"]
        self.assertEqual((sparc["human"]["subjects"], sparc["animal"]["subjects"]), (736, 3858))
        mw = self.program("MW")["species"]
        self.assertEqual((mw["human"]["subjects"], mw["animal"]["subjects"], mw["other"]["subjects"]), (1299, 1838, 377))
        exrna = self.program("ERCC_DCC")["species"]
        self.assertEqual(exrna["human"], {"subjects": 8548, "sex": 7325, "age": 7040})

    def test_plants_and_microbes_are_left_out_of_sex_and_age(self):
        checks = {c["id"]: c for c in self.program("MW")["dimensions"]["Characterization"]["checks"]}
        self.assertEqual(checks["subject_sex"]["total"], 3673 - 377)

    def test_finder_counts_humans_only(self):
        at = app("finder_page").run()
        at.radio(key="finder_species").set_value("human").run()
        self.assertClean(at)
        lines = [m.value for m in at.markdown if m.value.startswith("- **")]
        self.assertIn("- **ExRNA:** 7,040 of 8,548 human subjects have age and sex", lines)
        self.assertIn("- **SPARC:** 0 of 736 human subjects have age and sex (fewer than 100)", lines)
        at.radio(key="finder_species").set_value("animal").run()
        lines = [m.value for m in at.markdown if m.value.startswith("- **")]
        self.assertIn("- **ExRNA:** 32 of 32 animal subjects (not human) have age and sex (fewer than 100)", lines)

    def test_species_choice_carries_over_to_the_basket(self):
        keys = [k for k, p in BY_KEY.items() if p["program"] in ("ExRNA", "SPARC") and p["parent"]
                and not p["sub_projects"]]
        at = app("basket_page", hook=EXPORT_HOOK)
        at.session_state["basket"], at.session_state["needs"] = keys, ["sex", "age"]
        at.session_state["species"], at.session_state["basket_step"] = "human", STEPS[2]
        at.run()
        self.assertClean(at)
        for key, status, met, total in at.session_state["_review"]:
            self.assertEqual((status, met, total), expected_status(BY_KEY[key], "subject", ["sex", "age"], 100, "human"))

    def test_coverage_page_says_where_humans_have_no_sex_or_age(self):
        at = app("field_coverage_page").run()
        self.assertClean(at)
        self.assertIn("LINCS, Metabolomics Workbench, SPARC", at.info[0].value)


class ScoresUntouched(unittest.TestCase):
    def test_verified_scores(self):
        self.assertEqual({p["program"]: p["overall_score"] for p in COMPARISON["programs"]},
                         {"ERCC_DCC": 90, "HMP": 80, "KFDRC": 78, "LINCS": 80, "MW": 71, "SenNet": 94, "SPARC": 88})
        exrna = next(p for p in COMPARISON["programs"] if p["program"] == "ERCC_DCC")
        self.assertEqual(rc.count_meeting(exrna["combinations"], "subject", ["sex", "age"]), (7072, 8580))


if __name__ == "__main__":
    unittest.main()
