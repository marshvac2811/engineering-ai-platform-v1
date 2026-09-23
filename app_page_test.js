
const token = localStorage.getItem("engineering_ai_access_token");
const accountBox = document.getElementById("account");
const skillsStatusBox = document.getElementById("skills-status");
const skillsBox = document.getElementById("skills");
const skillDetailBox = document.getElementById("skill-detail");
const jobsBox = document.getElementById("jobs");
const detailBox = document.getElementById("job-detail");

function esc(value) {

    return String(value ?? "").replace(/[&<>"']/g, function(c) {
        return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
}


async function loadAccount() {
    if (!token) {
        accountBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await fetch("/v1/account", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Account request failed");
        }

        accountBox.innerHTML =
            "<p><strong>Tenant:</strong> " + esc(data.tenant_id) + "</p>" +
            "<p><strong>User ID:</strong> " + esc(data.user_id) + "</p>" +
            "<p><strong>Role:</strong> " + esc(data.role) + "</p>" +
            "<p><strong>Authentication:</strong> " + esc(data.auth_method) + "</p>" +
            "<p><strong>Scopes:</strong> " + esc((data.scopes || []).join(", ")) + "</p>";
    } catch (error) {
        accountBox.textContent = "Account load failed: " + error.message;
    }
}

async function loadSkills() {
    if (!token) {
        skillsStatusBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await fetch("/v1/skills", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Skills request failed");
        }

        const skills = data.skills || [];

        skillsStatusBox.innerHTML =
            "<p><strong>Registry:</strong> v" + esc(data.version) +
            " &nbsp; <strong>Status:</strong> " + esc(data.status) +
            " &nbsp; <strong>Total:</strong> " + esc(data.count) + "</p>";

        if (skills.length === 0) {
            skillsBox.innerHTML = "<p>No engineering skills registered.</p>";
            return;
        }

        skillsBox.innerHTML = skills.map(function(skill, index) {
            const executable = skill.integration_status === "integrated";

            return "<div style='border:1px solid #ddd;padding:12px;margin:10px 0;border-radius:8px'>" +
                "<div style='display:flex;justify-content:space-between;gap:12px;align-items:center'>" +
                "<div>" +
                "<p style='margin:0'><strong>" + esc(skill.skill_id) + "</strong></p>" +
                "<p style='margin:5px 0'><strong>Domain:</strong> " + esc(skill.domain || "-") +
                " &nbsp; <strong>Classification:</strong> " + esc(skill.classification || "-") + "</p>" +
                "<p style='margin:5px 0'><strong>Integration:</strong> " + esc(skill.integration_status || "-") +
                " &nbsp; <strong>Human Review:</strong> " + (skill.human_review_required ? "Yes" : "No") + "</p>" +
                "</div>" +
                "<button onclick='showSkill(" + index + ")'>View Inputs</button>" +
                "</div>" +
                "</div>";
        }).join("");

        window.engineeringSkills = skills;
    } catch (error) {
        skillsStatusBox.textContent = "Skills load failed: " + error.message;
        skillsBox.innerHTML = "";
    }
}

function showSkill(index) {
    const skill = (window.engineeringSkills || [])[index];

    if (!skill) {
        return;
    }

    function inputRows(items) {
        if (!items || items.length === 0) {
            return "<p>None</p>";
        }

        return "<ul>" + items.map(function(item) {
            return "<li><strong>" + esc(item.name) + "</strong> Ã¢â‚¬â€ " +
                esc(item.data_type || "value") +
                (item.allowed_values ? " Ã¢â‚¬â€ Allowed: " + esc(item.allowed_values.join(", ")) : "") +
                (item.description ? " Ã¢â‚¬â€ " + esc(item.description) : "") +
                "</li>";
        }).join("") + "</ul>";
    }

    skillDetailBox.style.display = "block";
    skillDetailBox.innerHTML =
        "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
        "<h3>Skill Detail</h3>" +
        "<p><strong>Skill ID:</strong> " + esc(skill.skill_id) + "</p>" +
        "<p><strong>Domain:</strong> " + esc(skill.domain || "-") + "</p>" +
        "<p><strong>Source Repository:</strong> " + esc(skill.source_repository || "-") + "</p>" +
        "<p><strong>Execution:</strong> " + esc(skill.execution || "-") + "</p>" +
        "<p><strong>Classification:</strong> " + esc(skill.classification || "-") + "</p>" +
        "<p><strong>Integration Status:</strong> " + esc(skill.integration_status || "-") + "</p>" +
        "<p><strong>Human Review Required:</strong> " + (skill.human_review_required ? "Yes" : "No") + "</p>" +
        "<h4>Required Inputs</h4>" +
        inputRows(skill.required_inputs) +
        "<h4>Optional Inputs</h4>" +
        inputRows(skill.optional_inputs) +
        "<h4>Conditional Inputs</h4>" +
        inputRows(skill.conditional_inputs) +
        "<button onclick='skillDetailBox.style.display=\"none\"'>Close</button>" +
        "</div>";
}

function parseJsonField(id, label) {
    const raw = document.getElementById(id).value.trim();

    if (!raw) {
        return {};
    }

    try {
        const value = JSON.parse(raw);

        if (!value || Array.isArray(value) || typeof value !== "object") {
            throw new Error(label + " must be a JSON object.");
        }

        return value;
    } catch (error) {
        throw new Error(label + " is invalid JSON: " + error.message);
    }
}

async function loadIntakeSkills() {
    const select = document.getElementById("intake-skill");

    if (!select || !window.engineeringSkills) {
        return;
    }

    const executableSkills = window.engineeringSkills.filter(function(skill) {
        return skill.integration_status === "integrated";
    });

    executableSkills.forEach(function(skill) {
        const option = document.createElement("option");
        option.value = skill.skill_id;
        option.textContent = skill.skill_id + " (" + (skill.domain || "Engineering") + ")";
        select.appendChild(option);
    });
}

function renderIntakePlan(plan, job) {
    const resultBox = document.getElementById("intake-result");
    const informationBox = document.getElementById("intake-information");

    resultBox.style.display = "block";
    informationBox.style.display = "none";

    const missing = plan.missing_inputs || [];
    const questions = plan.questions || [];
    const extracted = plan.extracted_inputs || {};

    resultBox.innerHTML =
        "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
        "<h3>Engineering Request Result</h3>" +
        "<p><strong>Status:</strong> " + esc(plan.status || "-") + "</p>" +
        "<p><strong>Selected Skill:</strong> " + esc(plan.selected_skill_id || "-") + "</p>" +
        "<p><strong>Confidence:</strong> " + esc(plan.confidence ?? "-") + "</p>" +
        "<p><strong>Job ID:</strong> " + esc((job || {}).job_id || "-") + "</p>" +
        "<p><strong>Job Status:</strong> " + esc((job || {}).status || "-") + "</p>" +
        "<p><strong>Routing Rationale:</strong> " + esc(plan.rationale || "-") + "</p>" +
        "<h4>Extracted / Provided Inputs</h4>" +
        "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(extracted, null, 2)) + "</pre>" +
        "<h4>Missing Inputs</h4>" +
        "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(missing, null, 2)) + "</pre>" +
        "<h4>Questions</h4>" +
        "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(questions, null, 2)) + "</pre>" +
        "</div>";

    if (missing.length > 0 && job && job.job_id) {
        informationBox.style.display = "block";

        informationBox.innerHTML =
            "<div style='border:1px solid #ddd;padding:16px;border-radius:8px'>" +
            "<h3>Provide Missing Engineering Information</h3>" +
            "<p>The job is waiting for additional inputs. Enter the missing values as JSON.</p>" +
            "<p><strong>Required:</strong> " + esc(missing.join(", ")) + "</p>" +
            "<p><strong>Questions:</strong></p>" +
            "<ul>" +
            questions.map(function(question) {
                return "<li>" + esc(question) + "</li>";
            }).join("") +
            "</ul>" +
            "<textarea id='missing-inputs' rows='6' style='width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccc;border-radius:8px' placeholder='{&quot;flow_m3hr&quot;:20,&quot;diameter_mm&quot;:80,&quot;straight_length_m&quot;:60,&quot;static_head_m&quot;:8,&quot;margin_pct&quot;:10}'></textarea>" +
            "<div style='margin-top:12px'>" +
            "<button onclick=&quot;provideMissingInformation('" + esc(job.job_id) + "')&quot;>Submit Missing Information</button>" +
            "</div>" +
            "</div>";
    }
}

async function submitEngineeringRequest() {
    const resultBox = document.getElementById("intake-result");

    try {
        const message = document.getElementById("intake-message").value.trim();

        if (!message) {
            throw new Error("Engineering Request is required.");
        }

        const skill = document.getElementById("intake-skill").value;
        const inputs = parseJsonField("intake-inputs", "Optional Inputs");
        const projectContext = parseJsonField("intake-context", "Project Context");

        const payload = {
            message: message,
            inputs: inputs,
            project_context: projectContext
        };

        if (skill) {
            payload.requested_skill_id = skill;
        }

        resultBox.style.display = "block";
        resultBox.innerHTML = "<p>Submitting engineering request...</p>";

        const response = await fetch("/v1/intake", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Engineering intake failed");
        }

        renderIntakePlan(data.plan || {}, data.job || {});
        await loadJobs();

        if (data.job && data.job.job_id) {
            await openJob(data.job.job_id);
        }
    } catch (error) {
        resultBox.style.display = "block";
        resultBox.innerHTML =
            "<p style='color:#b00020'><strong>Request failed:</strong> " +
            esc(error.message) + "</p>";
    }
}

async function provideMissingInformation(jobId) {
    try {
        const raw = document.getElementById("missing-inputs").value.trim();

        if (!raw) {
            throw new Error("Missing information JSON is required.");
        }

        let inputs;

        try {
            inputs = JSON.parse(raw);
        } catch (error) {
            throw new Error("Missing information must be valid JSON: " + error.message);
        }

        if (!inputs || Array.isArray(inputs) || typeof inputs !== "object") {
            throw new Error("Missing information must be a JSON object.");
        }

        const response = await fetch(
            "/v1/jobs/" + encodeURIComponent(jobId) + "/information",
            {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({inputs: inputs})
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Information update failed");
        }

        alert("Engineering information updated successfully.");

        await loadJobs();
        await openJob(jobId);
    } catch (error) {
        alert(error.message);
    }
}

async function loadJobs() {
    if (!token) {
        jobsBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await fetch("/v1/jobs", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Jobs request failed");
        }

        if (!data.jobs || data.jobs.length === 0) {
            jobsBox.innerHTML = "<p>No engineering jobs found.</p>";
            return;
        }

        jobsBox.innerHTML =
            "<p><strong>Total Jobs:</strong> " + esc(data.count) + "</p>" +
            data.jobs.map(function(job) {
                return "<div style='border:1px solid #ddd;padding:12px;margin:10px 0;border-radius:8px;cursor:pointer' " +
                    "onclick='openJob(\"" + esc(job.job_id) + "\")'>" +
                    "<p><strong>Job ID:</strong> " + esc(job.job_id) + "</p>" +
                    "<p><strong>Status:</strong> " + esc(job.status) + "</p>" +
                    "<p><strong>Skill:</strong> " + esc(job.skill_id || job.requested_skill_id || "Not selected") + "</p>" +
                    "<p><strong>Source:</strong> " + esc(job.source || "api") + "</p>" +
                    "</div>";
            }).join("");
    } catch (error) {
        jobsBox.textContent = error.message;
    }
}

async function openJob(jobId) {
    detailBox.style.display = "block";
    detailBox.innerHTML = "<p>Loading job detail...</p>";

    try {
        const response = await fetch("/v1/jobs/" + encodeURIComponent(jobId), {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Job request failed");
        }

        const result = data.result || {};
        const engineering = result.engineering_result || result;

        detailBox.innerHTML =
            "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
            "<h3>Job Detail</h3>" +
            "<p><strong>Job ID:</strong> " + esc(data.job_id) + "</p>" +
            "<p><strong>Tenant:</strong> " + esc(data.tenant_id) + "</p>" +
            "<p><strong>Status:</strong> " + esc(data.status) + "</p>" +
            "<p><strong>Source:</strong> " + esc(data.source) + "</p>" +
            "<p><strong>Requested Skill:</strong> " + esc(data.requested_skill_id || "-") + "</p>" +
            "<p><strong>Resolved Skill:</strong> " + esc(data.skill_id || "-") + "</p>" +
            "<p><strong>Attempt:</strong> " + esc(data.attempt) + "</p>" +

            "<h4>Inputs</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.inputs || {}, null, 2)) + "</pre>" +

            "<h4>Engineering Result</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(engineering || {}, null, 2)) + "</pre>" +

            "<h4>Warnings</h4>" +
            "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.warnings || [], null, 2)) + "</pre>" +

            "<h4>Errors</h4>" +
            "<pre style='white-space:pre-wrap;background:#ffebee;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.errors || [], null, 2)) + "</pre>" +

            "<h4>Lifecycle Events</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.events || [], null, 2)) + "</pre>" +

            "<p><strong>Human Review Required:</strong> " +
            (result.human_review_required ? "Yes" : "No") + "</p>" +

            "<p><strong>Dispatch:</strong> " +
            esc((data.dispatch_result || {}).mode || "manual") + "</p>" +

            "<div style='margin-top:15px'>" +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','enqueue')&quot;>Enqueue</button> " +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','process')&quot;>Process</button> " +
            "<button onclick=&quot;approveJob('" + esc(data.job_id) + "')&quot;>Approve</button> " +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','dispatch')&quot;>Dispatch</button> " +
            "<button onclick=&quot;detailBox.style.display='none'&quot;>Close</button>" +
            "</div>" +
            "</div>";
    } catch (error) {
        detailBox.innerHTML = "<p>" + esc(error.message) + "</p>";
    }
}

async function jobAction(jobId, action) {
    const response = await fetch(
        "/v1/jobs/" + encodeURIComponent(jobId) + "/" + action,
        {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: "{}"
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Action failed");
        return;
    }

    await loadJobs();
    await openJob(jobId);
}

async function approveJob(jobId) {
    const comment = prompt("Reviewer comment (optional):", "");

    if (comment === null) {
        return;
    }

    const response = await fetch(
        "/v1/jobs/" + encodeURIComponent(jobId) + "/approve",
        {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                reviewer: "browser-user",
                comment: comment
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Approval failed");
        return;
    }

    await loadJobs();
    await openJob(jobId);
}

loadAccount();
loadSkills().then(loadIntakeSkills);
loadJobs();

