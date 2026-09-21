export function showValidation(result) {
  const title = document.querySelector("#validation-title");
  const badge = document.querySelector("#validation-badge");
  const message = document.querySelector("#validation-message");
  const list = document.querySelector("#validation-errors");
  list.replaceChildren();

  if (result.valid) {
    title.textContent = "Scenario 校验通过";
    badge.textContent = "通过";
    badge.className = "badge success";
    message.textContent = "Schema、引用关系、飞机轮转、机组执勤、旅客行程及恢复时间窗均已通过检查。";
    return;
  }

  title.textContent = `发现 ${result.errors.length} 个校验问题`;
  badge.textContent = "已阻止";
  badge.className = "badge error";
  message.textContent = result.message || "无效数据不能进入优化求解。";
  for (const error of result.errors) {
    const item = document.createElement("li");
    const location = document.createElement("span");
    location.className = "error-location";
    location.textContent = error.location;
    item.append(location, document.createTextNode(error.message));
    list.append(item);
  }
}

export function showClientError(messageText) {
  showValidation({ valid: false, errors: [{ location: "$", message: messageText }] });
}
