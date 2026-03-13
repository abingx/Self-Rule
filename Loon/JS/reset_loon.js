const body = JSON.parse($request.body);
const model = typeof body.model === 'string' ? JSON.parse(body.model) : body.model;

const results = {};

for (const [policyName, selectName] of Object.entries(model)) {
  const success = $config.setSelectPolicy(policyName, selectName);
  results[policyName] = { select: selectName, success };
}

const modelSuccess = $config.setRunningModel(1);

$done({
  response: {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      runningModel: { model: '分流模式', success: modelSuccess },
      policies: results
    })
  }
});