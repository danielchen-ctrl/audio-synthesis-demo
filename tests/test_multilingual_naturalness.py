from __future__ import annotations

import sys
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.multilingual_naturalness import enforce_keywords_in_lines, polish_generated_lines, repair_dialogue_quality
from demo_app.rule_loader import clear_rule_cache, load_text_naturalness_rules


class MultilingualNaturalnessTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rule_cache()

    def test_rule_loader_accepts_naturalness_rules(self) -> None:
        payload = load_text_naturalness_rules()
        self.assertIn("Japanese", payload.get("languages", {}))
        self.assertIn("Spanish", payload.get("languages", {}))
        self.assertIn("Cantonese", payload.get("languages", {}))

    def test_polish_generated_lines_keeps_non_chinese_rule_path_available(self) -> None:
        lines = [("Speaker 1", "The most important thing is: <<Core:membership growth>>")]
        polished, meta = polish_generated_lines(lines, "English")
        self.assertEqual(polished, lines)
        self.assertEqual(meta["rewrite_count"], 0)

    def test_polish_generated_lines_rewrites_chinese_placeholders_and_noise(self) -> None:
        lines = [
            ("Speaker 1", "您好，我是Professional，是专业人士。我们开始吧。"),
            ("Speaker 2", "您好，我是Counterpart。乐意参加讨论。"),
            ("Speaker 1", "The most important thing is: <<Core:chronic disease management + follow-up system upgrade>>"),
            ("Speaker 2", "Risk Alert: 质量目标 requires attention, 完成率 currently at 82%, needs monitoring."),
        ]
        polished, meta = polish_generated_lines(
            lines,
            "Chinese",
            scenario="病人和医生讨论慢病复诊安排",
            core_content="慢病管理和复诊安排",
            profile={"work_content": "慢病复诊", "use_case": "问诊"},
        )
        rendered = "\n".join(text for _, text in polished)
        self.assertGreaterEqual(meta["rewrite_count"], 3)
        self.assertNotIn("Professional", rendered)
        self.assertNotIn("Counterpart", rendered)
        self.assertNotIn("<<Core:", rendered)
        self.assertNotIn("Risk Alert", rendered)
        self.assertRegex(polished[0][1], r"^你好，我是[\u4e00-\u9fff]{2,4}")
        self.assertRegex(polished[1][1], r"^你好，我是[\u4e00-\u9fff]{2,4}")
        self.assertTrue(any("慢病管理和复诊安排" in text or "病人和医生讨论慢病复诊安排" in text for _, text in polished))

    def test_polish_generated_lines_rewrites_boilerplate_sentences(self) -> None:
        lines = [
            ("Speaker 1", "基于刚才的讨论，我建议我们有几个选择："),
            ("Speaker 1", "方案1: 方案一是快速推进，两周内完成，但可能需要您这边配合加班。"),
            ("Speaker 1", "方案2: 方案二是稳步推进，一个月完成，时间更充裕，质量更有保障。"),
        ]
        polished, _ = polish_generated_lines(lines, "Chinese", scenario="季度项目讨论", core_content="", profile={})
        self.assertEqual(polished[0][1], "现在大致有两种思路，我们可以一起权衡哪种更合适。")
        self.assertEqual(polished[1][1], "一种做法是先从最关键的部分开始，边推进边看效果。")
        self.assertEqual(polished[2][1], "另一种做法是先把方案准备充分，再整体往下推。")

    def test_enforce_keywords_in_lines_weaves_missing_keywords_naturally_for_chinese(self) -> None:
        lines = [
            ("Speaker 1", "你好，我们先把现在的情况梳理一下。"),
            ("Speaker 2", "好，我最想知道接下来应该怎么推进。"),
        ]
        updated, missing = enforce_keywords_in_lines(
            lines,
            ["慢病管理", "复诊率"],
            "Chinese",
            scenario="医院慢病随访讨论",
            core_content="慢病管理策略",
            profile={"work_content": "慢病随访"},
        )
        self.assertEqual(missing, ["慢病管理", "复诊率"])
        rendered = "\n".join(text for _, text in updated)
        self.assertIn("慢病管理", rendered)
        self.assertIn("复诊率", rendered)
        self.assertNotIn("明确提到这些关键词", rendered)
        self.assertTrue(any("慢病管理" in text or "复诊率" in text for _, text in updated))

    def test_repair_dialogue_quality_rebuilds_flat_secondary_lines(self) -> None:
        lines = [
            ("Speaker 1", "你好，我是王芳，我们先把系统稳定性这件事聊明白。"),
            ("Speaker 2", "这个我需要回去确认一下，明天给您答复可以吗？"),
            ("Speaker 3", "我会认真思考这个问题，准备好之后再向您汇报。"),
            ("Speaker 1", "现在大致有两种思路，我们可以一起权衡哪种更合适。"),
            ("Speaker 2", "我明白了，这个确实需要注意。"),
        ]
        repaired, meta = repair_dialogue_quality(
            lines,
            "Chinese",
            scenario="测试开发讨论上线前的系统稳定性和风险控制",
            core_content="接口超时、降级策略、回滚预案、灰度发布",
            profile={"work_content": "系统稳定性", "use_case": "评审会"},
            target_word_count=900,
            people_count=3,
            keywords=["接口超时", "降级策略"],
        )
        rendered = "\n".join(text for _, text in repaired)
        speaker_two_lines = [text for speaker, text in repaired if speaker == "Speaker 2"]
        speaker_three_lines = [text for speaker, text in repaired if speaker == "Speaker 3"]
        self.assertTrue(meta["repaired"])
        self.assertGreaterEqual(len(speaker_two_lines), 3)
        self.assertGreaterEqual(len(speaker_three_lines), 3)
        self.assertIn("接口超时", rendered)
        self.assertTrue(any("降级策略" in text for text in speaker_two_lines + speaker_three_lines))
        self.assertGreater(len(rendered.replace("\n", "")), 700)

    def test_repair_dialogue_quality_respects_target_speakers_and_content_length(self) -> None:
        lines = [
            ("Speaker 1", "你好，我们先把稳定性与上线准入这件事聊明白。"),
            ("Speaker 2", "这个我需要回去确认一下，明天给您答复可以吗？"),
            ("Speaker 3", "我会认真思考这个问题，准备好之后再向您汇报。"),
            ("Speaker 4", "我明白了，这个确实需要注意。"),
        ]
        repaired, meta = repair_dialogue_quality(
            lines,
            "Chinese",
            title="稳定性与上线准入",
            scenario="围绕稳定性与上线准入进行真实自然的多轮评审会对话",
            core_content="核心对话内容：对话中必须明确体现这些关键词——接口超时，降级策略，回滚预案",
            profile={"work_content": "稳定性与上线准入", "use_case": "评审会"},
            target_word_count=1000,
            people_count=3,
            keywords=["接口超时", "降级策略", "回滚预案"],
        )
        speakers = sorted({speaker for speaker, _ in repaired})
        content_length = sum(len(re.sub(r"\s+", "", text)) for _, text in repaired)
        rendered = "\n".join(text for _, text in repaired)
        self.assertTrue(meta["repaired"])
        self.assertEqual(speakers, ["Speaker 1", "Speaker 2", "Speaker 3"])
        self.assertGreaterEqual(content_length, 960)
        self.assertNotIn("这件事", repaired[0][1])
        self.assertNotIn("进行真实自然的多轮", rendered)
        self.assertIn("接口超时", rendered)
        self.assertIn("降级策略", rendered)
        self.assertIn("回滚预案", rendered)
        speaker_two_lines = [text for speaker, text in repaired if speaker == "Speaker 2"]
        speaker_three_lines = [text for speaker, text in repaired if speaker == "Speaker 3"]
        self.assertTrue(set(speaker_two_lines) - set(speaker_three_lines))
        self.assertTrue(set(speaker_three_lines) - set(speaker_two_lines))

    def test_repair_dialogue_quality_uses_generation_context_roles_and_stricter_length(self) -> None:
        lines = [
            ("Speaker 1", "你好，我们先看一下当前情况。"),
            ("Speaker 2", "我觉得还有一些地方需要确认。"),
            ("Speaker 3", "好的，那我再补充一点。"),
        ]
        repaired, meta = repair_dialogue_quality(
            lines,
            "Chinese",
            title="支付项目上线评审",
            scenario="围绕支付项目中的关键风险进行讨论",
            core_content="重点关注支付接入、下单回调、退款安全、对账差错、稳定性准入",
            profile={"work_content": "支付项目", "use_case": "测试开发｜支付项目"},
            target_word_count=1000,
            people_count=3,
            keywords=["支付接入", "退款安全", "稳定性准入"],
            generation_context={
                "domain": "测试开发",
                "scene_type": "支付项目",
                "scene_goal": "围绕支付链路接入、异常兜底和上线风险展开讨论",
                "deliverable": "形成测试范围、风险清单和上线准入结论",
                "role_briefs": ["测试负责人", "服务端开发", "产品经理"],
                "discussion_axes": ["支付接入", "下单回调", "退款安全", "对账差错", "稳定性准入"],
            },
        )
        content_length = sum(len(re.sub(r"\s+", "", text)) for _, text in repaired)
        rendered = "\n".join(text for _, text in repaired)
        self.assertTrue(meta["repaired"])
        self.assertGreaterEqual(content_length, 980)
        self.assertLessEqual(content_length, 1035)
        self.assertIn("支付接入", rendered)
        self.assertIn("退款安全", rendered)
        self.assertIn("稳定性准入", rendered)
        self.assertTrue(any("服务端开发" in text for _, text in repaired))
        self.assertTrue(any("产品经理" in text for _, text in repaired))

    def test_repair_dialogue_quality_fixed_template_regression_samples(self) -> None:
        seed_lines = [
            ("Speaker 1", "你好，我们先看一下当前情况。"),
            ("Speaker 2", "我觉得还有一些地方需要确认。"),
            ("Speaker 3", "好的，那我再补充一点。"),
        ]
        samples = [
            {
                "title": "支付项目上线评审",
                "scenario": "围绕支付项目中的关键风险进行讨论",
                "core_content": "重点关注支付接入、下单回调、退款安全、对账差错、稳定性准入",
                "profile": {"work_content": "支付项目", "use_case": "测试开发｜支付项目"},
                "target_word_count": 1000,
                "people_count": 3,
                "keywords": ["支付接入", "退款安全", "稳定性准入"],
                "generation_context": {
                    "domain": "测试开发",
                    "scene_type": "支付项目",
                    "scene_goal": "围绕支付链路接入、异常兜底和上线风险展开讨论",
                    "deliverable": "形成测试范围、风险清单和上线准入结论",
                    "role_briefs": ["测试负责人", "服务端开发", "产品经理"],
                    "discussion_axes": ["支付接入", "下单回调", "退款安全", "对账差错", "稳定性准入"],
                },
                "must_include": ["灰度", "回滚", "支付接入"],
            },
            {
                "title": "慢病随访复盘",
                "scenario": "围绕慢病随访中的复查安排和病情变化进行讨论",
                "core_content": "重点关注症状变化、用药执行、复查节点、风险提示",
                "profile": {"work_content": "慢病随访", "use_case": "医疗健康｜慢病随访"},
                "target_word_count": 900,
                "people_count": 3,
                "keywords": ["症状变化", "复查节点", "风险提示"],
                "generation_context": {
                    "domain": "医疗健康",
                    "scene_type": "慢病随访",
                    "scene_goal": "围绕患者当前症状、复查安排和治疗配合展开交流",
                    "deliverable": "形成明确的复查安排、风险提示和家庭配合动作",
                    "role_briefs": ["随访医生", "患者本人", "家属"],
                    "discussion_axes": ["症状变化", "用药执行", "复查节点", "风险提示"],
                },
                "must_include": ["复查", "用药", "风险提示"],
            },
            {
                "title": "会员复购提升会",
                "scenario": "围绕会员复购提升中的活动策略和门店配合展开讨论",
                "core_content": "重点关注会员分层、活动策略、门店配合、效果验证",
                "profile": {"work_content": "会员复购", "use_case": "零售行业｜会员复购"},
                "target_word_count": 950,
                "people_count": 4,
                "keywords": ["会员分层", "活动策略", "效果验证"],
                "generation_context": {
                    "domain": "零售行业",
                    "scene_type": "会员复购",
                    "scene_goal": "围绕触达策略、门店配合和活动效果展开讨论",
                    "deliverable": "形成会员复购提升方案和执行节奏",
                    "role_briefs": ["会员运营负责人", "门店负责人", "活动运营", "数据分析师"],
                    "discussion_axes": ["会员分层", "活动策略", "门店配合", "效果验证"],
                },
                "must_include": ["会员分层", "门店", "复购"],
            },
        ]

        for sample in samples:
            must_include = sample["must_include"]
            payload = {key: value for key, value in sample.items() if key != "must_include"}
            repaired, meta = repair_dialogue_quality(seed_lines, "Chinese", **payload)
            rendered = "\n".join(text for _, text in repaired)
            content_length = sum(len(re.sub(r"\s+", "", text)) for _, text in repaired)
            speakers = sorted({speaker for speaker, _ in repaired})
            self.assertEqual(len(speakers), sample["people_count"])
            self.assertGreaterEqual(content_length, int(sample["target_word_count"] * 0.98))
            self.assertLessEqual(content_length, int(sample["target_word_count"] * 1.03))
            self.assertGreaterEqual(meta["quality_metrics"]["score"], 0.9)
            for term in must_include:
                self.assertIn(term, rendered)


if __name__ == "__main__":
    unittest.main()
