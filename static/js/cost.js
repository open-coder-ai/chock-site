// "What does a late finding cost you?": plain arithmetic on the five inputs.
// Without this file the page still shows the formula and the worked example.

const host = document.querySelector("[data-cost]");

const fmt = (value) =>
  Number(value.toFixed(1)).toLocaleString("en-US", { maximumFractionDigits: 1 });

// Hours, money and days saved per release; `share` is a percentage (0-100).
export function savings({ findings, share, minutes, rate, days }) {
  const hours = ((findings * share) / 100) * (minutes / 60);
  return { hours, money: hours * rate, days: (days * share) / 100 };
}

// The five values, or null when any is empty, negative or above its max.
function read(root) {
  const values = {};
  for (const input of root.querySelectorAll("input[name]")) {
    const text = input.value.trim();
    const value = Number(text);
    const max = input.max === "" ? Infinity : Number(input.max);
    if (text === "" || !Number.isFinite(value) || value < 0 || value > max) return null;
    values[input.name] = value;
  }
  return values;
}

function update() {
  const invalid = host.querySelector("#calc-invalid");
  const out = (name) => host.querySelector(`[data-out="${name}"]`);
  const values = read(host);
  invalid.hidden = values !== null;
  if (values === null) {
    for (const name of ["hours", "money", "days"]) out(name).textContent = "–";
    return;
  }
  const result = savings(values);
  out("hours").textContent = fmt(result.hours);
  out("money").textContent = `$${Math.round(result.money).toLocaleString("en-US")}`;
  out("days").textContent = fmt(result.days);
}

if (host) {
  host.addEventListener("input", update);
  update();
}
