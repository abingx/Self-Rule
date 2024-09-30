async function aiChat() {
  const url = $glm_url;
  const key = $glm_key;
  const model = "glm-4-flash";
  const prompt = "你是中英互译专家，直接输出翻译后的内容，不要输出任何其他内容"; 
  const question = $searchText || $pasteboardContent;
  try {
    const response = await $http({
      url: url,
      method: "POST",
      header: {
        "Authorization": key,
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