async function aiChat() {
  const url = $glm_url; // 自定义变量
  const key = $glm_key; // 自定义变量
  const model = "glm-4-flash"; // 智谱清言免费模型，自行设定
  const prompt = "你是中英互译专家，我输入中文就直接输出翻译后英文，我输入英文就直接输出翻译后的中文，不要输出任何其他内容"; //根据实际自行定义
  const question = $searchText || $pasteboardContent; //优先脚本对话框，如为空调用剪贴板
  const body = {
    model: model,
    messages: [
      { role: "system", content: prompt },
      { role: "user", content: question }
    ]
  };
  try {
    const response = await $http({
      url: url,
      method: "POST",
      header: { 
        "Authorization": key,
        "Content-Type": "application/json"
      },
      body: body
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