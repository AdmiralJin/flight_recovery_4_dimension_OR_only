export function showValidation(result) {
  const title = document.querySelector("#validation-title");
  const badge = document.querySelector("#validation-badge");
  const message = document.querySelector("#validation-message");
  const list = document.querySelector("#validation-errors");
  list.replaceChildren();

  if (result.valid) {
    title.textContent = "Scenario is valid";
    badge.textContent = "Passed";
    badge.className = "badge success";
    message.textContent = "Schema, references, rotations, duties, itineraries and recovery-window checks passed.";
    return;
  }

  title.textContent = `${result.errors.length} validation issue${result.errors.length === 1 ? "" : "s"}`;
  badge.textContent = "Blocked";
  badge.className = "badge error";
  message.textContent = result.message || "Invalid data cannot enter optimization.";
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

