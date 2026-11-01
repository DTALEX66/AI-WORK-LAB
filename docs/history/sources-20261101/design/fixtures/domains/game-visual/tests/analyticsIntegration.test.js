import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const gameSource = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');

function countTrackEvent(name) {
  return (gameSource.match(new RegExp(`trackEvent\\('${name}'`, 'g')) || []).length;
}

test('browser game runtime wires analytics to key gameplay and ad events', () => {
  assert.match(gameSource, /import \{ trackEvent \} from '\.\/analytics\.js';/);

  for (const eventName of [
    'game_start',
    'game_over',
    'revive_start',
    'revive_reward',
    'hidden_log_start',
    'hidden_log_unlock',
    'fake_ending_trigger',
    'action_click',
    'anomaly_trigger',
  ]) {
    assert.ok(countTrackEvent(eventName) >= 1, `${eventName} should be tracked in src/game.js`);
  }
});
