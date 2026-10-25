# Learning Claude Code agents, step by step

## 0. Setup (5 min)
```bash
npm install -g @anthropic-ai/claude-code
mkdir virtual-testbench && cd virtual-testbench
# copy the .claude/ folder and CLAUDE.md from this kit into here
git init
claude            # start a session in this folder
```
Inside the session type `/agents` and you should see your 4 agents listed.

## What an agent is
One Markdown file in `.claude/agents/`:
- **Frontmatter**: `name`, `description` (tells the main Claude WHEN to use it), `tools` (what it may touch), `model`
- **Body**: the agent's system prompt (its role and rules)

Each agent runs in its **own fresh context**: it doesn't see your chat history.
So it only knows what you tell it, plus CLAUDE.md and the files it reads.
That's why the hand-off file (`docs/test_plans/...`) matters.

Project agents live in `.claude/agents/` (shared via git).
Personal agents live in `~/.claude/agents/` (all your projects).

---

## Lesson 1: Call one agent
```
Use the mentor agent to explain what a Control Pilot signal is in IEC 61851.
```
Answer the quiz. Notice: mentor has no Write tool, so it CAN'T change files.

**Exercise:** open `mentor.md`, change "2 quiz questions" to 3, restart `claude`, ask again.
You just edited an agent's behaviour.

## Lesson 2: Planner -> file
```
Use the test-planner agent to plan tests for a fake SCPI power meter
that answers *IDN? and MEAS:POW? and returns an error for unknown commands.
```
Open `docs/test_plans/`. Read the plan yourself and fix anything wrong. **You are the lead.**

## Lesson 3: Chain agents (the real workflow)
```
Use the coder agent to implement the plan in docs/test_plans/scpi_power_meter.md.
Then use the reviewer agent to review the result.
```
Read the reviewer's table. Then:
```
Use the coder agent to fix the High items from the review.
```

## Lesson 4: Watch the tool limits work
```
Use the reviewer agent to fix the bug in sim/scpi_power_meter.py.
```
It will refuse or fail: no Edit tool. That's the safety design.
**Lesson:** give each role only the tools it needs.

## Lesson 5: Make your own agent
Type `/agents` -> "Create new agent", or copy a file. Ideas:
- `standards-checker`: compares a test plan against a pasted VDE/OCPP clause
- `log-analyst`: reads Modbus/OCPP logs and finds anomalies (read-only)
- `ci-engineer`: writes the GitHub Actions workflow

Write a **sharp description** so Claude picks it automatically, then test it without naming it:
```
Analyse logs/ocpp_session.json for errors.
```
Did Claude pick `log-analyst` by itself? If not, improve the description.

---

## Command cheat sheet
| Goal | Type in Claude Code |
|---|---|
| List/create/edit agents | `/agents` |
| Call a specific agent | `Use the <name> agent to ...` |
| Chain | `Use A to ..., then use B to ...` |
| Run in parallel | `Use the reviewer and mentor agents in parallel to ...` |
| Let Claude choose | just describe the task; it matches `description` |

## Good habits
1. One role = one job. If a prompt says "and also...", split the agent.
2. Hand off through files, not memory.
3. Read every output before passing it on. Agents speed you up; they don't replace your judgement.
4. Commit after each lesson (`git commit`) so you can diff what the agent changed.

## You already know this pattern
VS Code Copilot custom agents (`.github/agents/*.agent.md`) have the same idea:
a Markdown prompt + tool list per role. Skills transfer 1:1.
