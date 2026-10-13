import { open } from '@arxo/law';
import { loadModel } from '@arxo/canon-fide-chess/chess';
import { game, white, getCaseInput } from '@arxo/canon-fide-chess/examples/arbiter';
const model = await loadModel();
const chess = await open(model.spec, { offline: true, local: { packages: { [model.spec]: model.package } } });
for (const name of ['SecondIllegal', 'SecondIllegalNoMate']) {
  const input = getCaseInput(name);
  const loss = await chess.truth('game_lost_by', [game, white], input);
  const draw = await chess.truth('game_drawn', [game], input);
  console.log(name, { loss: [loss.evaluationStatus, loss.truthStatus], draw: [draw.evaluationStatus, draw.truthStatus] });
}
