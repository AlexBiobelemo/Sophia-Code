(() => {
  // Lightweight, dependency-free password strength scoring.
  // Output score: 0..4 (Weak .. Very strong)
  function scorePassword(pw) {
    const password = String(pw || "");
    if (!password) return { score: 0, label: "—", hints: ["Start typing a password."] };

    const hints = [];

    const lower = password.toLowerCase();
    const length = password.length;

    const hasLower = /[a-z]/.test(password);
    const hasUpper = /[A-Z]/.test(password);
    const hasDigit = /\d/.test(password);
    const hasSymbol = /[^A-Za-z0-9]/.test(password);
    const variety = [hasLower, hasUpper, hasDigit, hasSymbol].filter(Boolean).length;

    function hasLongRun(s, minRun) {
      let run = 1;
      for (let i = 1; i < s.length; i++) {
        run = s[i] === s[i - 1] ? run + 1 : 1;
        if (run >= minRun) return true;
      }
      return false;
    }

    function hasSimpleSequence(s) {
      // Detect increasing sequences like 1234, abcd, qwer, etc.
      const seqs = ["qwerty", "asdf", "zxcv", "12345", "09876", "1qaz", "qazwsx"];
      if (seqs.some((p) => s.includes(p))) return true;
      const norm = s.replace(/[^a-z0-9]/g, "");
      for (let i = 0; i + 3 < norm.length; i++) {
        const a = norm.charCodeAt(i);
        const b = norm.charCodeAt(i + 1);
        const c = norm.charCodeAt(i + 2);
        const d = norm.charCodeAt(i + 3);
        if (b === a + 1 && c === b + 1 && d === c + 1) return true;
        if (b === a - 1 && c === b - 1 && d === c - 1) return true;
      }
      return false;
    }

    // Base points (0..7)
    let points = 0;

    // Length scoring
    if (length < 8) {
      hints.push("Use at least 8 characters.");
    } else if (length < 12) {
      points += 1;
    } else if (length < 16) {
      points += 2;
    } else if (length < 24) {
      points += 3;
    } else {
      points += 4;
    }

    // Variety bonus
    if (variety <= 1) {
      hints.push("Mix uppercase, lowercase, numbers, and symbols.");
    } else if (variety === 2) {
      points += 1;
    } else if (variety === 3) {
      points += 2;
    } else {
      points += 3;
    }

    // Penalties
    if (/^(.)\1+$/.test(password) || hasLongRun(password, 6)) {
      points -= 3;
      hints.push("Avoid long repeats (e.g., 'aaaaaa').");
    }

    if (hasSimpleSequence(lower)) {
      points -= 2;
      hints.push("Avoid sequences like 1234, abcd, qwerty.");
    }

    // Common password fragments
    if (/(^|[^a-z])password([^a-z]|$)|letmein|admin|welcome|iloveyou|monkey|dragon/.test(lower)) {
      points -= 3;
      hints.push("Avoid common passwords or obvious words.");
    }

    // Year/date-like patterns are easy to guess
    if (/(19|20)\d{2}/.test(lower)) {
      points -= 1;
      hints.push("Avoid years or date-like patterns.");
    }

    // Very low uniqueness
    const uniq = new Set(password.split("")).size;
    const uniqRatio = uniq / Math.max(1, length);
    if (length >= 8 && uniqRatio < 0.45) {
      points -= 1;
      hints.push("Use a less repetitive mix of characters.");
    }

    points = Math.max(0, points);

    // Map points -> 0..4
    let score = 0;
    if (points <= 1) score = 0;
    else if (points <= 3) score = 1;
    else if (points <= 5) score = 2;
    else if (points === 6) score = 3;
    else score = 4;

    // Guardrails: short passwords never reach strong tiers
    if (length < 12) score = Math.min(score, 2);
    if (length < 8) score = 0;

    const label = ["Weak", "Fair", "Good", "Strong", "Very strong"][score] || "—";

    if (score >= 3) {
      hints.length = 0;
      hints.push("Looks strong. A longer passphrase is even better.");
    } else if (hints.length === 0) {
      hints.push("Add length and more character variety for a stronger password.");
    }

    return { score, label, hints };
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
