# fide.laws.chess

FIDE Laws of Chess (в силе с 01.01.2023) — полный свод: ст. 1–12, приложения A и B

> Independent demonstration model. It is not an implementation by or
> for an authority and does not establish legal accuracy or completeness.
> For a real case, rely on the official texts and competent bodies.

## Package snapshot

| Item | Value |
|---|---|
| Version | `0.1.1` |
| Namespace | `urn:fide:laws:clir:chess` |
| Semantics | `law.core/0.2.11` |
| Dependencies | None declared |

## Run an example

Install the CLI as described in the [repository README](../../README.md).
From the repository root:

```sh
cd packages/fide.laws.chess
law test . --file tests/01-touch-move-requires-judgment.lawtest --json
```

Success checks the declared expectations of the model; it does not certify
that the model covers the whole benefit or every possible case.

## Scope and inputs

The executable scope is defined by the rules and declared scenarios in this
snapshot. Each rule has its own dates, prerequisites and source anchors.
Use the supplied facts and any explicitly selected readings of the scenario;
do not infer wider coverage from the subject named above.

The package author records these limitations (retained from
[package-info.json](package-info.json)):

- Общий шахматный движок и полная достижимость позиции не вычисляются. Новый producer вычисляет геометрию известного полного четырёхфигурного K/Q/R кадра, один двухполуходовой свидетель мата и невозможность мата у одинокого белого короля; вне этого среза остаётся протокольный режим.
- Legacy king_cannot_be_checkmated/checked_player сохраняются для статей 5.1.2 и 7.5.5. Новый Game-keyed producer статьи 6.9 не требует готовых mate/capability/safety фактов; неизвестные или конфликтные записи не дают заключения.
- Намеренность касания фигуры — внешнее суждение арбитра (piece_touched_intentionally, §47.3): без суждения ответ REQUIRES_JUDGMENT, отсутствие суждения не превращается в утверждение о намеренности.
- Текст нотации (приложение C) не разбирается: запись хода на бланке — предъявленный факт протокола, а не строка, которую пакет читает.
- Приложение D (игра с незрячими и слабовидящими) — организационные обязанности ассистента и устройства без исполнимых последствий для исхода; закреплено фрагментом, не формализовано.
- Решения арбитра «по наилучшему суждению» без критериев в Законах (статьи 6.10, 6.11.3, 7.1) не исполняются; оценочные признаки с последствиями (6.7.1, 6.11.4, 8.7, 11.1, 11.5, 11.7) — внешнее суждение арбитра §47.3.

| Inspect | What it contains |
|---|---|
| [law.toml](law.toml) | Package identity, dependencies and declared scenario groups |
| [law.lock](law.lock) | Exact dependency, semantics and resource pins |
| [tests/](tests/) | Declared scenarios and their fixtures |
| [sources/](sources/) | Captured source material; individual reproduction terms apply |
| [sources.law](sources.law) | Model declarations and source references |

## Reproduction and rights

See the [repository instructions](../../README.md) for rebuilding
a source package and restoring any withheld sources. The [repository licence](../../LICENSE)
covers the model code; captured publisher texts keep their own terms in
[NOTICE](../../NOTICE) and [package-info.json](package-info.json).
