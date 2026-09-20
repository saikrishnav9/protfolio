function inferGithub() {
  const host = location.hostname;
  if (host.endsWith("github.io")) {
    const user = host.split(".")[0];
    const parts = location.pathname.split("/").filter(Boolean);
    const repo = parts[0] && parts[0] !== "pulse" ? parts[0] : `${user}.github.io`;
    return {
      user: `https://github.com/${user}`,
      repo: `https://github.com/${user}/${repo}`,
    };
  }
  return { user: "", repo: "" };
}

function el(html) {
  const wrap = document.createElement("div");
  wrap.innerHTML = html.trim();
  return wrap.firstElementChild;
}

function renderProfile() {
  const profile = window.PROFILE || {};
  const gh = inferGithub();
  document.title = `${profile.name || "Portfolio"} — ${profile.role || "Data Engineer"}`;
  const set = (id, value) => {
    const node = document.getElementById(id);
    if (node && value) node.textContent = value;
  };
  set("name-line", profile.name);
  set("role-line", profile.role);
  set("headline-line", profile.headline);
  set("summary-line", profile.summary);
  set("location-line", profile.location);
  set("foot-name", profile.name);

  const github = profile.github || gh.user;
  const links = [];
  if (profile.email) links.push(`<a class="btn primary" href="mailto:${profile.email}">Email</a>`);
  if (profile.phone) {
    const tel = profile.phone.replace(/[^\d+]/g, "");
    links.push(`<a class="btn ghost" href="tel:${tel}">${profile.phone}</a>`);
  }
  if (profile.linkedin) links.push(`<a class="btn ghost" href="${profile.linkedin}">LinkedIn</a>`);
  if (github) links.push(`<a class="btn ghost" href="${github}">GitHub</a>`);
  if (profile.resume) links.push(`<a class="btn ghost" href="${profile.resume}">Resume PDF</a>`);
  document.getElementById("contact-links").innerHTML = links.join("");
  return { profile, github, repo: gh.repo };
}

function renderProjects(repo) {
  const root = document.getElementById("projects");
  const projects = window.PROJECTS || [];
  root.replaceChildren(
    ...projects.map((project) => {
      const href = project.repo || repo;
      return el(`
        <article class="project">
          <p class="kicker">Featured project · ${project.year}</p>
          <h3>${project.name}</h3>
          <p class="one-liner">${project.oneLiner}</p>
          <p>${project.problem} ${project.approach}</p>
          <ul class="highlights">${(project.highlights || []).map((item) => `<li>${item}</li>`).join("")}</ul>
          <div class="tags">${(project.tags || []).map((tag) => `<span>${tag}</span>`).join("")}</div>
          <div class="hero-actions">
            <a class="btn primary" href="${project.demo}">Open live demo</a>
            ${href ? `<a class="btn ghost" href="${href}">Repository</a>` : ""}
          </div>
        </article>
      `);
    })
  );
}

function renderExperience(profile) {
  const root = document.getElementById("experience");
  root.replaceChildren(
    ...(profile.experience || []).map((job) =>
      el(`
        <article class="job">
          <p class="when">${job.dates}</p>
          <div>
            <h3>${job.title}</h3>
            <p class="org">${job.client ? `${job.company} · Client: ${job.client}` : job.company}</p>
            <ul>${job.bullets.map((item) => `<li>${item}</li>`).join("")}</ul>
          </div>
        </article>
      `)
    )
  );
}

function renderSkills(profile) {
  const board = document.getElementById("skill-board");
  board.replaceChildren(
    ...(profile.skillGroups || []).map((group) =>
      el(`
        <div class="skill-row">
          <strong>${group.label}</strong>
          <div class="chips">${group.items.map((item) => `<span>${item}</span>`).join("")}</div>
        </div>
      `)
    )
  );

  const edu = document.getElementById("edu-certs");
  const schools = (profile.education || [])
    .map(
      (item) =>
        `<article><strong>${item.credential}</strong><p>${item.school} · ${item.year}</p></article>`
    )
    .join("");
  const certs = (profile.certifications || []).map((item) => `<article><strong>${item}</strong></article>`).join("");
  edu.innerHTML = `<div class="edu">${schools}${certs}</div>`;
}

const ctx = renderProfile();
renderProjects(ctx.repo);
renderExperience(ctx.profile);
renderSkills(ctx.profile);
