# Constitution: olist-ai-analyst

1. **Code checks the model.** SQL safety, number grounding and scoring are done by code, not by
   another model.
2. **Numbers come from runs.** Every figure in the README is produced by a committed eval run,
   linked to it; nothing is typed by hand.
3. **No fitting the eval.** Questions are not tuned to the model; a reworded question is
   listed with the reason.
4. **Free and local**: Ollama on a CPU runner, no paid key.
5. **Every change is tested** (pytest, ruff) before it is pushed.
