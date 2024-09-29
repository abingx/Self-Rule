async function aiChat() {
  const url = $qwen_url + "/v1/chat/completions";
  const key = $qwen_key;
  const model = "qwen-max";
  const prompt = "你是我的购物评价助手，如果输入"产品名称/好评"，则输出一段好评；如果输入"产品名称/中评"，则输出一段中评；如果输入"产品名称/差评"，则输出一段差评。评价60-100字左右，内容侧重使用感受，通俗易懂口语化，可以按照1、2、3、来分段，并加入emoji表情。";
  const question = $searchText || $pasteboardContent;
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
        "Authorization": `Bearer ${key}`,
        "Content-Type": "application/json"
      },
      body: body,
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