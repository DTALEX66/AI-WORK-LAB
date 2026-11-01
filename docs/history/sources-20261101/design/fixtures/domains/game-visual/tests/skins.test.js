import test from 'node:test';
import assert from 'node:assert/strict';

import elevatorSkin from '../src/skins/elevator/skin.json' with { type: 'json' };
import securitySkin from '../src/skins/security/skin.json' with { type: 'json' };
import factorySkin from '../src/skins/factory/skin.json' with { type: 'json' };
import subwaySkin from '../src/skins/subway/skin.json' with { type: 'json' };
import hospitalSkin from '../src/skins/hospital/skin.json' with { type: 'json' };

const skins = [
  ['elevator', elevatorSkin],
  ['security', securitySkin],
  ['factory', factorySkin],
  ['subway', subwaySkin],
  ['hospital', hospitalSkin],
];

const REQUIRED_TEXT_KEYS = [
  ['meta', 'id'],
  ['meta', 'name'],
  ['meta', 'subtitle'],
  ['monitor', 'initial'],
  ['actionLabels', 'openDoor'],
  ['actionLabels', 'closeDoor'],
  ['actionLabels', 'moveUp'],
  ['actionLabels', 'moveDown'],
  ['actionLabels', 'emergencyStop'],
  ['actionLabels', 'restartSystem'],
  ['actionLabels', 'inspectLog'],
  ['actionLabels', 'unlockHiddenLog'],
  ['actionFailMessages', 'unknownAction'],
  ['actionFeedback', 'emergencyStop_fail'],
  ['statusLabels', 'panelTitle'],
  ['statusLabels', 'floor'],
  ['statusLabels', 'door'],
  ['statusLabels', 'direction'],
  ['statusLabels', 'passengers'],
  ['statusLabels', 'power'],
  ['statusLabels', 'stability'],
  ['statusLabels', 'anomalyLevel'],
  ['statusLabels', 'reviveCount'],
  ['statusLabels', 'adHintsCount'],
  ['statusLabels', 'hiddenLogsCount'],
  ['canvasLabels', 'countdown'],
  ['canvasLabels', 'monitorPanel'],
  ['canvasLabels', 'actionPanel'],
  ['canvasLabels', 'logPanel'],
  ['canvasLabels', 'forceAnomaly'],
  ['canvasLabels', 'failureTitle'],
  ['canvasLabels', 'failureEyebrow'],
  ['canvasLabels', 'monitorSignalStable'],
  ['canvasLabels', 'monitorSignalUnstable'],
  ['canvasLabels', 'monitorSignalCorrupted'],
  ['canvasLabels', 'monitorThreat'],
  ['canvasLabels', 'failureMetricStability'],
  ['canvasLabels', 'failureMetricAnomaly'],
  ['canvasLabels', 'failureMetricRemaining'],
  ['actionLogMessages', 'inspectLog_hiddenRecords'],
  ['failure', 'defaultHint'],
  ['failure', 'firstRunAdvice'],
  ['fakeEnding', 'text'],
  ['fakeEnding', 'truthContent'],
  ['ui', 'viewAd'],
  ['ui', 'revealTruth'],
  ['ui', 'decodePrefix'],
  ['ui', 'anomalyEventLog'],
  ['ui', 'startTitle'],
  ['ui', 'startCopy'],
  ['ui', 'startChecklist'],
  ['ui', 'startFailureRulesTitle'],
  ['ui', 'startFailureRules'],
  ['ui', 'startButton'],
  ['ui', 'hiddenLogCaptured'],
];

function getByPath(obj, path) {
  return path.reduce((value, key) => value?.[key], obj);
}

test('all shipped skins expose required text keys', () => {
  for (const [name, skin] of skins) {
    for (const path of REQUIRED_TEXT_KEYS) {
      const value = getByPath(skin, path);
      assert.equal(typeof value, 'string', `${name} missing ${path.join('.')}`);
      assert.ok(value.length > 0, `${name} empty ${path.join('.')}`);
    }
  }
});

test('all shipped skins provide complete anomaly and hidden-log catalogues', () => {
  for (const [name, skin] of skins) {
    assert.ok(Array.isArray(skin.anomalies), `${name} anomalies must be an array`);
    assert.ok(skin.anomalies.length >= 12, `${name} should have at least 12 anomalies`);

    const ids = new Set();
    for (const anomaly of skin.anomalies) {
      assert.ok(anomaly.id, `${name} anomaly missing id`);
      assert.ok(!ids.has(anomaly.id), `${name} duplicate anomaly id ${anomaly.id}`);
      ids.add(anomaly.id);
      assert.equal(typeof anomaly.title, 'string', `${name}/${anomaly.id} missing title`);
      assert.equal(typeof anomaly.monitor, 'string', `${name}/${anomaly.id} missing monitor`);
      assert.equal(typeof anomaly.adHint, 'string', `${name}/${anomaly.id} missing adHint`);
      assert.ok(anomaly.effects && typeof anomaly.effects === 'object', `${name}/${anomaly.id} missing effects`);

      const hidden = skin.hiddenLogs?.[anomaly.id];
      assert.ok(hidden, `${name}/${anomaly.id} missing hidden log`);
      assert.equal(typeof hidden.title, 'string', `${name}/${anomaly.id} hidden log missing title`);
      assert.equal(typeof hidden.content, 'string', `${name}/${anomaly.id} hidden log missing content`);
    }
  }
});

test('subway skin validates the fourth-skin production workflow', () => {
  assert.equal(subwaySkin.meta.id, 'subway');
  assert.equal(subwaySkin.meta.name, '地铁末班调度室');
  assert.match(subwaySkin.actionLabels.openDoor, /屏蔽门/);
  assert.match(subwaySkin.canvasLabels.monitorSignalStable, /SIGNAL: CLEAR/);

  const serialized = JSON.stringify(subwaySkin);
  for (const forbidden of ['电梯', '轿厢', '楼层']) {
    assert.doesNotMatch(serialized, new RegExp(forbidden), `subway skin should not keep elevator term: ${forbidden}`);
  }
});

test('hospital skin validates the fifth-skin production workflow', () => {
  assert.equal(hospitalSkin.meta.id, 'hospital');
  assert.equal(hospitalSkin.meta.name, '深夜医院值班台');
  assert.match(hospitalSkin.actionLabels.openDoor, /病房门|隔离门/);
  assert.match(hospitalSkin.canvasLabels.monitorSignalStable, /VITALS|WARD|ICU/);

  const ids = hospitalSkin.anomalies.map((anomaly) => anomaly.id);
  assert.equal(new Set(ids).size, ids.length, 'hospital anomaly ids should be unique');
  assert.ok(hospitalSkin.anomalies.length >= 12, 'hospital should ship with at least 12 anomalies');

  const serialized = JSON.stringify(hospitalSkin);
  for (const forbidden of ['电梯', '轿厢', '楼层', '站台', '列车', '屏蔽门']) {
    assert.doesNotMatch(serialized, new RegExp(forbidden), `hospital skin should not keep old-domain term: ${forbidden}`);
  }
});
