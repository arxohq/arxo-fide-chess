import { open, type CaseInput } from '@arxo/law';
import { loadModel, type ModelSpec } from '@arxo/canon-fide-chess';
import { loadModel as loadChess } from '@arxo/canon-fide-chess/chess';
import { getCaseInput, game, white, king, type CaseName } from '@arxo/canon-fide-chess/examples/arbiter';
const spec: ModelSpec = 'fide.laws.chess@0.1.1';
const model = await loadChess();
const chess = await open(model.spec, { offline: true, local: { packages: { [model.spec]: model.package } } });
const input: CaseInput = getCaseInput('SecondIllegal');
await loadModel(spec);
await chess.truth('game_lost_by', [game, white], input);
await chess.truth('game_drawn', [game], input);
await chess.truth('must_move_first_touched_piece', [white, king], getCaseInput('TouchIntentUnknown'));
await chess.collect('extra_time_awarded_seconds', [game, white, '?seconds'], input);
await chess.truth('fide.laws.chess::game_lost_by', [game, white], input);
// @ts-expect-error exact model specs only
await loadModel('fide.laws.chess');
// @ts-expect-error misspelled relation
await chess.truth('game_lost_b', [game, white], input);
// @ts-expect-error exact fixture names only
const wrong: CaseName = 'SecondIllegall';
void wrong;
