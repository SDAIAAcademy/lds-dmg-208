# مختبرات LDS-DMG-208

كل مختبر صفحة (`D1_1_matching.html` وما بعدها) تُفتح من صفحة المقرر. المشارك لا يكتب برمجة: يغيّر ملف قواعد أو جدولًا، ويشغّل أوامر جاهزة من أداة المقرر `kit/`.

## التشغيل

على الحاسوب، بـ [uv](https://docs.astral.sh/uv/) ودون تثبيت Python يدويًا:

```
cd labs
uv run kit/match.py files/matching/rules_start.yml
```

أول تشغيل ينزّل المكتبات المثبتة في `pyproject.toml` و`uv.lock` (Splink 5.0.0 وDuckDB وPyYAML)، وكل تشغيل بعده نحو عشر ثوانٍ على معالج حاسوب محمول. لا نموذج يُنزّل ولا مفتاح يلزم.

في Google Colab: افتح `notebook.ipynb`، وشغّل خلية الإعداد (تنسخ المستودع وتثبّت `requirements-colab.txt`)، ثم خلايا المختبر.

كل أمر يضيف سطرًا إلى `out/run_log.jsonl`: الأمر، وبصمة كل ملف قرأه، والأرقام التي طبعها. هذا السجل جزء مما يُسلَّم.

## نقطة البداية والحل لكل مختبر

| المختبر | يبدأ من | الحل المرجعي |
|---|---|---|
| 1.1 قواعد المطابقة | `files/matching/rules_start.yml` | `solutions/reference/rules_reference.yml` |
| 1.2 السجلات الذهبية | `files/golden/survivorship_start.yml` (عناقيد معتمدة، لا ناتج 1.1) | `solutions/reference/survivorship_reference.yml` |
| 2.1 قوائم الرموز | `files/codes/` (قائمة خارجية، ومسودة فيها أخطاء، وقوالب) | `solutions/reference/codes/v1.0` و`v1.1` |
| 2.2 قائمة الإشراف | `files/queue/` (عشرون حالة، واقتراحات مكتوبة سلفًا، وقالبان) | `solutions/reference/decision_log_reference.csv` و`workflow_reference.yml` |
| المشروع الختامي | `files/capstone/brief.txt` | `solutions/capstone.md` |

الأرقام المتوقعة في `solutions/answer_key.md`. للتحقق من كل الحلول:

```
uv run solutions/check.py
```

يطبع الأرقام وPASS لكل مختبر، ويكتب في `out/` الذي يتجاهله git؛ احذفه بعد ذلك.

## الذكاء الاصطناعي

لا يستدعي أي مختبر نموذجًا. في المختبر 2.2 كُتبت اقتراحات «النموذج» سلفًا في `files/queue/model_suggestions.csv` على العرض العام وحده (`model_view.csv`)، وخمسة منها من عشرين خاطئة عمدًا. لا يدخل أي صف من ملفات الموردين أداة ذكاء اصطناعي توليدي: السجل الكامل مصنف «مقيدًا» في الحالة.

## البيانات

كل الملفات اصطناعية يولّدها `_tools/prepare_files.py` (مكتبة Python القياسية فقط، بذرة ثابتة 208)، ثم `_tools/prepare_queue.py` لحالات القائمة. الاستثناء `files/codes/iso_3166_2_sa.csv`: رموز المناطق الثلاث عشرة في المعيار ISO 3166-2:SA وأسماؤها المختصرة، وهي حقائق عامة تحققنا منها في [ويكي بيانات](https://www.wikidata.org/wiki/Property:P300) (الخاصية P300، بيانات مفتوحة CC0). لإعادة التوليد:

```
uv run --no-project _tools/prepare_files.py
uv run _tools/prepare_queue.py
```
