"""Evidence-based attribution, independent of any particular model/test names."""
import json
import unittest

from app.services.llm.local import _Analysis, _ground, _speaker_identities, _source_schema, _turns


class AttributionTest(unittest.TestCase):
    def attribute(self, transcript, speaker, quote, guessed_author=None):
        answer = _Analysis.model_validate_json(json.dumps({
            "summary": "Test", "tasks": [{"task": "Test action", "assignee": None,
            "deadline": None, "assigned_by": guessed_author,
            "source_speaker": speaker, "source_text": quote}],
        }))
        _ground(answer, transcript)
        return answer.tasks[0].assigned_by

    def test_missing_author_is_bound_for_different_names_and_labels(self):
        for name, label in [("Раушан", "VOICE_7"), ("Илья", "Speaker B"), ("Мария Петрова", "S3")]:
            with self.subTest(name=name):
                text = f"{label}: Меня зовут {name}.\n{label}: Проверить документ, исполнитель не назначен."
                self.assertEqual(self.attribute(text, label, "Проверить документ"), name)

    def test_russian_and_kazakh_identity_evidence(self):
        for intro, name in [("Менің атым Әлия.", "Әлия"), ("Менің есімім Нұрлан.", "Нұрлан"),
                            ("Моё имя Ольга.", "Ольга"), ("My name is Emma.", "Emma")]:
            text = f"[X] {intro}\n[X] Проверить результат."
            self.assertEqual(self.attribute(text, "X", "Проверить результат."), name)
            self.assertEqual(_speaker_identities(_turns(text))["X"].evidence, intro)

    def test_only_the_source_speakers_identity_is_used(self):
        text = "A: Меня зовут Борис.\nB: Меня зовут Дана.\nB: Проверить результат."
        self.assertEqual(self.attribute(text, "B", "Проверить результат.", "Борис"), "Дана")

    def test_mentioned_assignee_is_not_the_author(self):
        text = "A: Светлана, проверь результат."
        self.assertIsNone(self.attribute(text, "A", "Светлана, проверь результат.", "Светлана"))

    def test_conflicting_self_introductions_abstain(self):
        text = "A: Меня зовут Ольга.\nA: Меня зовут Дарья.\nA: Проверить результат."
        self.assertIsNone(self.attribute(text, "A", "Проверить результат.", "Ольга"))

    def test_reported_or_quoted_introduction_is_not_identity(self):
        for intro in ['Он сказал: Меня зовут Арман.', '«Меня зовут Арман.»',
                      'Не говорите: Меня зовут Арман.', 'Меня зовут не Арман.', 'Я Согласен.']:
            text = f"A: {intro}\nA: Проверить результат."
            self.assertIsNone(self.attribute(text, "A", "Проверить результат.", "Арман"))

    def test_reported_instruction_does_not_make_narrator_the_author(self):
        for report in ['Олег попросил проверить результат.', 'Олег сказал: «Проверить результат».',
                       'Арман есепті тексеруді тапсырды.']:
            text = f"A: Меня зовут Мария.\nA: {report}"
            self.assertIsNone(self.attribute(text, "A", report, "Мария"))

    def test_missing_source_never_supplies_author(self):
        self.assertIsNone(self.attribute("A: Меня зовут Салтанат.", "", "", "Салтанат"))

    def test_bad_citation_still_fails_before_binding(self):
        for speaker, quote in [("B", "Проверить результат."), ("A", "Выдуманная цитата")]:
            with self.assertRaises(ValueError):
                self.attribute("A: Меня зовут Роман.\nA: Проверить результат.", speaker, quote)

    def test_repeated_same_identity_is_not_a_conflict(self):
        text = "A: Меня зовут Жанна.\nA: Меня зовут Жанна.\nA: Проверить результат."
        self.assertEqual(self.attribute(text, "A", "Проверить результат."), "Жанна")

    def test_generation_schema_only_offers_original_sources(self):
        props = _source_schema("A: Первый текст.\nB: Другой текст.")["$defs"]["_Task"]["properties"]
        self.assertEqual(props["source_speaker"]["enum"], ["", "A", "B"])
        self.assertEqual(props["source_text"]["enum"], ["", "Первый текст.", "Другой текст."])

    def test_absence_statement_is_not_a_deadline(self):
        for phrase, expected in [("Срок не определён", None), ("Мерзім белгіленбеген", None),
                                 ("не позднее пятницы", "не позднее пятницы"),
                                 ("завтра", "завтра")]:
            text = "A: Проверить результат. " + phrase
            answer = _Analysis(summary="Test", tasks=[dict(task="Test", assignee=None,
                deadline=phrase, assigned_by=None, source_speaker="A", source_text="Проверить результат.")])
            _ground(answer, text)
            self.assertEqual(answer.tasks[0].deadline, expected)


if __name__ == "__main__":
    unittest.main()
