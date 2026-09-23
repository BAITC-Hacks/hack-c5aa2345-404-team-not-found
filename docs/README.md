# Документация SAMRUK KAZYNA

Документы описывают исходники main на основе `a61ed5a` и опубликованные отчёты
команды от 23.09.2026. Готовность компонентов и сквозного сценария различается.

## Жюри и пользователю

| Задача | Документ |
| --- | --- |
| Понять проблему, результат и текущую готовность | [Главный README](../README.md) |
| Проверить решение по шагам | [Сценарий жюри](jury-guide.md) |
| Собрать EXE и открыть демо | [Windows-клиент](desktop/README.md) |
| Запустить API-каркас | [Backend](../backend/README.md) |
| Подготовить локальные модели | [Local AI](local-ai/README.md) |
| Сопоставить проект с критериями оценивания | [Чек-лист](hackathon-checklist.md) |

## Техническому специалисту

- [Архитектура и границы реализации](architecture.md).
- [Целевой HTTP API и фактические маршруты](api-contract.md).
- [Проверки: команды, отчёты и ограничения](verification.md).
- [Интеграция и отличия прежнего Streamlit-клиента](integration-notes.md).
- [Desktop handoff: ранее проверенная сборка](desktop/handoff.md).
- [Local AI handoff: железо, версии, модели и измерения](local-ai/handoff.md).
- [Синтетические примеры](../samples/README.md).

## Участникам команды

[Roadmap](../ROADMAP.md), [workflow](team-workflow.md), [ролевые задания](team-prompts.md)
и [AGENTS.md](../AGENTS.md). Ролевые задания описывают ожидаемую работу, а не
доказывают её выполнение. Сохранённый [Streamlit UI](../frontend/README.md) и
эксперимент pywebview/PyInstaller не являются основным Windows-клиентом.
