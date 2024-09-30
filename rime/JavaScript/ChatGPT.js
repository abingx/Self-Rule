async function aiChat() {
  const url = $chatgpt_url + "/v1/chat/completions";
  const key = $chatgpt_key;
  const model = "o1-mini";
  const prompt = "你是一位 AI 助手，能够回答得专业且准确";
  const question = $searchText || $pasteboardContent;
  try {
    const response = await $http({
      url: url,
      method: "POST",
      header: {
        "Authorization": `Bearer ${key}`,
        "Content-Type": "application/json"
      },
      body: {
        model: model,
        messages: [
          { role: "system", content: prompt },
          { role: "user", content: question }
        ]
      },
    });
    if (response.response.statusCode !== 200) {
      return "请求失败";
    }
    const jsonData = JSON.parse(response.data);
    return jsonData.choices[0].message.content;
  } catch (error) {
    $log(error);
    return "";
  }
}
async function output() {
  const result = await aiChat();
  return result;
}