export async function loadExample() {
  const response = await fetch("/api/examples/toy_case_001");
  if (!response.ok) throw new Error(`Example request failed (${response.status})`);
  return response.json();
}

export async function validateScenario(data) {
  const response = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response.json();
}

