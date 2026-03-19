(() => {
  function scorePassword(pw) {
    const password = String(pw || "");
    if (!password) return { score: 0, label: "—", hints: ["Start typing a password."] };

    const hints = [];
    let score = 0;

    const length = password.length;
    if (length >= 8) score += 1; else hints.push("Use at least 8 characters.");
    if (length >= 12) score += 1;

    const hasLower = /[a-z]/.test(password);
    const hasUpper = /[A-Z]/.test(password);
    const hasDigit = /\d/.test(password);
    const hasSymbol = /[^A-Za-z0-9]/.test(password);

    const variety = [hasLower, hasUpper, hasDigit, hasSymbol].filter(Boolean).length;
    if (variety >= 2) score += 1; else hints.push("Mix letters and numbers/symbols.");
    if (variety >= 3) score += 1;
    if (variety === 4) score += 1;

    // Penalize very common patterns
    const lower = password.toLowerCase();
    if (/password|qwerty|letmein|admin|12345|123456|iloveyou/.test(lower)) {
      score = Math.max(0, score - 2);
      hints.push("Avoid common passwords or sequences.");
    }
    if (/^(.)\1+$/.test(password)) {
      score = Math.max(0, score - 2);
      hints.push("Avoid repeating the same character.");
    }

    const clamped = Math.max(0, Math.min(4, Math.floor(score / 2)));
    const label = ["Weak", "Fair", "Good", "Strong", "Very strong"][clamped] || "—";

    if (clamped >= 3) hints.length = 0;
    if (hints.length === 0) hints.push("Looks good. Consider a passphrase for extra strength.");

    return { score: clamped, label, hints };
  }

  function setStrength(container, result) {
    if (!container) return;
    container.classList.remove("strength-0", "strength-1", "strength-2", "strength-3", "strength-4");
    container.classList.add(`strength-${result.score}`);

    const text = container.querySelector("#passwordStrengthText");
    if (text) text.textContent = `Strength: ${result.label}`;

    const hintsEl = container.querySelector("#passwordStrengthHints");
    if (hintsEl) {
      hintsEl.innerHTML = result.hints.slice(0, 2).map((h) => `<div class="strength-hint">${h}</div>`).join("");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input =
      document.querySelector('input[name="password"]') ||
      document.getElementById("password");
    const strength = document.getElementById("passwordStrength");
    if (!input || !strength) return;

    const update = () => setStrength(strength, scorePassword(input.value));
    input.addEventListener("input", update);
    input.addEventListener("blur", update);
    update();
  });
})();

