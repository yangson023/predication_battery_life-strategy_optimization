import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.parse_bts_step_xml_metadata import parse_and_write, parse_bts_step_xml


UTF8_WITH_GB2312_DECL = """<?xml version="1.0" encoding="GB2312"?>
<root>
  <config type="Step File" version="17" date="20260512172057" Guid="unit-guid">
    <Head_Info>
      <Creator Value="LTH" />
      <PN Value="Li-Cu" />
      <Remark Value="CE-50μL-醚类电解液" />
    </Head_Info>
    <Whole_Prt>
      <Record><Main><Time Value="30000" /></Main></Record>
    </Whole_Prt>
    <Step_Info Num="5">
      <Step1 Step_ID="1" Step_Type="4">
        <Limit><Main><Time Value="36000000" /></Main></Limit>
        <Protect><Main><Volt><Upper Value="40000" /><Lower Value="-40000" /></Volt></Main></Protect>
      </Step1>
      <Step2 Step_ID="2" Step_Type="2">
        <Limit><Main><Curr Value="1.54" /><Cap Value="5544" /></Main></Limit>
        <Protect><Main><Volt><Upper Value="40000" /><Lower Value="-40000" /></Volt></Main></Protect>
      </Step2>
      <Step3 Step_ID="3" Step_Type="1">
        <Limit><Main><Curr Value="1.54" /><Stop_Volt Value="10000" /></Main></Limit>
      </Step3>
      <Step4 Step_ID="4" Step_Type="5">
        <Limit><Other><Start_Step Value="2" /><Cycle_Count Value="500" /></Other></Limit>
      </Step4>
      <Step5 Step_ID="5" Step_Type="6" />
    </Step_Info>
  </config>
</root>
"""


GB2312_XML = """<?xml version="1.0" encoding="GB2312"?>
<root>
  <config type="Step File" version="17" date="20260414174500" Guid="gb-guid">
    <Head_Info>
      <Creator Value="LTH" />
      <PN Value="Li-Li" />
      <Remark Value="酯类电解液50uL" />
    </Head_Info>
    <Step_Info Num="1">
      <Step1 Step_ID="1" Step_Type="4">
        <Limit><Main><Time Value="36000000" /></Main></Limit>
      </Step1>
    </Step_Info>
  </config>
</root>
"""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class BtsStepXmlMetadataParserTests(unittest.TestCase):
    def test_utf8_bytes_with_gb2312_declaration_parse_chinese_remark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "unit.xml"
            xml.write_bytes(UTF8_WITH_GB2312_DECL.encode("utf-8"))

            result = parse_bts_step_xml(xml, xml_label="unit")

            self.assertEqual(result.decode_codec, "utf-8")
            self.assertEqual(result.inferred_experiment_date, "2026-05-12")
            self.assertEqual(result.creator, "LTH")
            self.assertIn("醚类电解液", result.remark_raw)
            self.assertIn("ether_based", result.electrolyte_hint)
            self.assertFalse(result.training_allowed_now)

    def test_gb2312_encoded_xml_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "gb.xml"
            xml.write_bytes(GB2312_XML.encode("gb2312"))

            result = parse_bts_step_xml(xml, xml_label="gb")

            self.assertEqual(result.inferred_experiment_date, "2026-04-14")
            self.assertEqual(result.remark_raw, "酯类电解液50uL")
            self.assertIn("ester_based", result.electrolyte_hint)

    def test_capacity_and_protocol_fields_are_flagged_for_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "unit.xml"
            xml.write_bytes(UTF8_WITH_GB2312_DECL.encode("utf-8"))

            result = parse_bts_step_xml(xml, xml_label="unit")

            self.assertEqual(result.capacity_limit_raw, 5544)
            self.assertEqual(result.capacity_limit_raw_unit_guess, "probable_mAs")
            self.assertIn("capacity_limit_raw_unit_needs_confirmation", result.unit_flagged_fields)
            self.assertIn("终止原因", result.fields_need_manual_confirmation)

    def test_outputs_are_written_and_are_not_training_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml = root / "unit.xml"
            out = root / "out"
            xml.write_bytes(UTF8_WITH_GB2312_DECL.encode("utf-8"))

            parse_and_write(xml, out, xml_label="unit")

            summary = read_csv(out / "bts_step_xml_metadata_summary.csv")
            steps = read_csv(out / "bts_step_protocol_steps.csv")
            self.assertEqual(summary[0]["training_allowed_now"], "False")
            self.assertEqual(len(steps), 5)
            self.assertTrue((out / "bts_step_metadata_report.json").exists())
            self.assertTrue((out / "bts_step_metadata_report.md").exists())

    def test_missing_xml_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                parse_bts_step_xml(Path(tmp) / "missing.xml")


    def test_multiple_loop_counts_are_retained_in_protocol_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "multi-loop.xml"
            multi_loop = UTF8_WITH_GB2312_DECL.replace(
                '<Step5 Step_ID="5" Step_Type="6" />',
                '<Step5 Step_ID="5" Step_Type="5"><Limit><Other><Start_Step Value="2" /><Cycle_Count Value="20" /></Other></Limit></Step5>\n'
                '      <Step6 Step_ID="6" Step_Type="6" />',
            ).replace('Step_Info Num="5"', 'Step_Info Num="6"')
            xml.write_bytes(multi_loop.encode("utf-8"))

            result = parse_bts_step_xml(xml, xml_label="multi")

            self.assertEqual(result.cycle_count, "500;20")
            self.assertEqual(result.start_step, "2;2")


if __name__ == "__main__":
    unittest.main()
