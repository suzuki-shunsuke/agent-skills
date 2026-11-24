---
name: dev-flow
description: Defines how to go from design through implementation, pull request creation, review, and merge. Avoids problems common in AI-driven implementation and review, such as humans being unable to understand the changes, or pull requests drifting from their original scope and bloating. Use when a human asks for an implementation large enough to need design, when asked to investigate or organize information to decide what to do, or when you created a pull request without design and want to bring it into the flow. Do not use for small changes such as typo fixes, or for reviewing pull requests created by others (use the pr-review skill).
---

## Principles

- Design thoroughly before coding
  - Deepen the human's understanding
  - Document the design and have humans and AI review it, to reduce rework before implementation
- Define the pull request's scope in advance and do not stray from it
- Limit human decisions to three points: approving the overview (Background / What / Why / Scope), approving the specification (Behaviour), and deciding to merge. In between, the AI proceeds autonomously
  - What a human needs in order to apply the brakes is an understanding of the intent, scope, and specification, not of the implementation approach or details
  - The overview alone can leave specification-level misunderstandings, so the human checks the specification before implementation
  - Record decisions made along the way so the human can verify them at the end

## Starting the Flow

Start this flow when a human asks for an implementation, even if the skill is not explicitly invoked.

However, do not start it for small changes that need no design, such as typo fixes, dependency updates, or fixes of a few lines.
If a human judges it necessary and explicitly invokes the skill, start the flow regardless of the size of the change.

1. Look in tasks/ for a task corresponding to the request
1. If there is none, generate the task documents from the templates before writing any code, write Background / What / Why / Scope / Out of Scope, and ask the human for a review (start from step 1 of Steps). If the request is too vague to write these, ask what they want implemented
    - If what to do (What) is not yet decided and investigation or organizing information is needed to decide it, start an investigation task (see "Investigation Tasks")
1. If there is one, determine the progress from task.yaml's `type` and `status`, which sections are filled in, and the decision log in details.md, and resume from the next step

For each task, open a new pane in herdr, start Claude Code there, and proceed.

### When a Pull Request Already Exists

Normally the flow starts before the pull request is created, but sometimes design and other steps were skipped and a pull request already exists.
This only covers pull requests you (a human or an agent) created and will fix and manage with this flow from now on. If asked to review a pull request created by someone else, use the pr-review skill instead of this flow.
In that case too, generate documents from the pull request and bring it into the flow, so that the human can understand the pull request and review and fix it properly.

1. Write Background / What / Why / Scope / Out of Scope / Behaviour / Implementation Plan / PR Explanation from the pull request's contents
1. Get the human's approval of Background / What / Why / Scope / Out of Scope and Behaviour. If the pull request contains out-of-scope changes, point them out at this time
1. Join step 3 of Steps at the pull request review. If the code changes during review, rewrite the PR Explanation at the end

## Document Layout

```
tasks/
  <task id>/
    task.yaml
    <task id>.md
    details.md
    pr-explanation.md
```

- The agent proposes `<task id>` and the human confirms it
- Create documents per task. If you decide to split a task during design, split the documents too. Scope / Out of Scope is the criterion for whether to accept review comments, so if it is not split per task, judgments become inconsistent
  - When creating multiple pull requests, create documents per pull request as sub tasks, and make each pull request's scope clear. Reduce rework by settling the pull requests needed for the whole parent task and each pull request's specification before creating any pull request
- `task.yaml`: the task's metadata, generated from templates/task.yaml (see "task.yaml")
- `<task id>.md`: the README-equivalent document, generated from templates/design.md (templates/investigation.md for investigation tasks). Give it a unique name rather than something like README.md so it is distinguishable by file name
- `details.md`: records what was discussed with the agent during design and the decisions made in review. Keeping it as primary information matters, but it grows large, is hard for humans to get the point of, and wastes context if the agent reads it all every time, so keep it separate from `<task id>.md`
- `pr-explanation.md`: the PR Explanation (see "PR Explanation Format"). Not created for investigation tasks

### task.yaml

Write the task's metadata in `tasks/<task id>/task.yaml`. This lets tools (such as `yq`) list and search tasks. Keeping it separate from the documents lets you read and write only the metadata without reading the documents.

```yaml
name: aws-provider-v6 # same as the task id
description: Update the Terraform AWS Provider to v6
# implementation - a task that implements and creates a pull request
# investigation - a task that investigates and organizes information to decide what to do (see "Investigation Tasks")
type: implementation
# backlog - not started this week
# todo - doing this week but not started
# overview-design - designing the overview. Includes waiting for human approval (step 1 of Steps, step 1 of investigation tasks)
# detail-design - designing the details. Includes waiting for human approval (step 2 of Steps)
# doing - the AI is autonomously implementing or investigating (step 3 of Steps, step 2 of investigation tasks)
# in-review - waiting for the human's final decision. Pull request review and merge decision, or approval of the conclusion for investigation tasks (step 4 of Steps, step 3 of investigation tasks)
# pending - stopped because a blocker was found or the priority dropped
# cancel - decided not to do it
# done - completed
status: doing # backlog, todo, overview-design, detail-design, doing, in-review, pending, cancel, done
tags:
  - terraform
claude_sessions:
  - id: xxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    description: Summary of the session and how it relates to the task
parent_task: "" # for a sub task, the parent's task id
sub_tasks: [] # task ids of the children
derived_from: "" # for a task created from an investigation task's conclusion, the original investigation task's task id
derived_tasks: [] # task ids of tasks created from this investigation task's conclusion
repositories:
  - https://github.com/aquaproj/aqua-registry
issues:
  - https://github.com/aquaproj/aqua-registry/issues/64946
pull_requests:
  - https://github.com/aquaproj/aqua-registry/pull/64947
```

- Update `status` as the steps progress (on entering each step, set the corresponding value above, and set `done` when the pull request is merged). While waiting for human approval, do not set `pending`; keep the value of that step
- When you create a pull request or issue, add it to `pull_requests` / `issues`
- When you create a sub task, set both the parent's `sub_tasks` and the child's `parent_task`
- When you create a task from an investigation task, set both the investigation task's `derived_tasks` and the new task's `derived_from`. Distinguish these from sub tasks (one task split per pull request)

## Steps

### 1. Settle the Direction (Human Approves)

1. Generate task.yaml and the documents from the templates. Skip if they already exist
1. Write Background / What / Why / Scope / Out of Scope
    - This stage confirms that the problem being solved and the direction are right before thinking about details
    - See "Writing the Overview" for how to write it
1. Have an agent review it, and repeat until it converges (see "Review Rules")
1. Get the human's approval of Background / What / Why / Scope / Out of Scope. This becomes the basis for every later decision

#### Writing the Overview

The overview lets a reader judge the problem and direction without reading code.

- Background: write what the reader needs to know as a premise. What the related features or commands do (e.g. what `aqua vacuum` is, what `--init` is for), the history so far, and so on. Make sure the human never wonders "what was this again?"
- What / Why: write in terms of behaviour as seen by users. Do not write about internal implementation such as function or type names. If needed, write those in Implementation Plan or details.md
  - When the change itself is about internal implementation, such as refactoring, it may talk about internal implementation. Even then, make sure the reader can grasp the premises from Background
- For changes that alter behaviour, write Before / After in What, showing what changes and how by contrast (e.g. the current result and the result after the change when running the same command)
- Where possible, write the current problem in Why as bug reproduction steps to make it easy to picture
  - How To Reproduce: steps (example configuration files and commands)
  - Expected Behaviour: the expected behaviour
  - Actual Behaviour: the actual behaviour
  - This may be omitted for changes it does not fit, such as new features or improvements
- Write Scope / Out of Scope / Open Questions in terms of behaviour as much as possible too

### 2. Settle the Specification (Human Approves)

1. Design the details for implementation, and write the discussion in details.md
1. Write the specification and behaviour the implementation must satisfy in Behaviour, and the implementation approach in Implementation Plan. Like the overview, write Behaviour in terms of behaviour as seen by users, and put function names and the like in Implementation Plan
1. Have an agent review the specification and implementation approach together, and repeat until it converges
1. Get the human's approval of Behaviour. Implementation Plan is not subject to approval

### 3. Proceed Autonomously (AI Runs)

1. Implement
1. Create the pull request
1. Have an agent review the pull request, and repeat until it converges
1. Write the PR Explanation (see "PR Explanation Format"). It is a document for humans, so write it against the code as it stands after review has finished changing it

Create a dedicated git worktree for implementation. Delete the worktree once the pull request is merged.

At this stage, follow these rules.

- If the approved Background / What / Why / Scope / Out of Scope / Behaviour needs to change, do not decide on your own; ask the human, update the documents, then proceed
- If a problem with the implementation approach is found, fix the Implementation Plan before implementing
- Do not include out-of-scope comments or improvements in the pull request; write them in Follow-ups. Do not create issues
- For each review comment, record in details.md whether it was accepted or rejected and why

### 4. The Human Decides

1. Open the final documents and the PR Explanation with `mo` (`mo tasks/<task id>/<task id>.md tasks/<task id>/pr-explanation.md`). The human reads the final documents, the decision log in details.md, and the PR Explanation, and asks questions in conversation with the agent. The agent answers and, if needed, reflects the answers in the documents and the PR Explanation (mo reloads automatically on save)
1. The human decides on the pull request
1. The human decides which Follow-ups become issues, and the agent creates them
1. The human merges

## Investigation Tasks

If what to do (What) is not yet clear and investigation or organizing information is needed to decide it, create an investigation task.
An investigation task's What is "investigating and organizing information" itself. Once what to do concretely is decided, create a separate task to implement it.

Proceeding as an implementation task with a vague What leaves Scope / Out of Scope unsettled, so they cannot serve as review criteria.
Separating investigation from implementation lets the human approve the investigation's conclusion (what to do) before the implementation task starts through the normal flow.

- Set `type` in task.yaml to `investigation`, and generate the document from templates/investigation.md
- Do not change code or create pull requests. Even if you write code experimentally for verification, do not turn it into a pull request
- Even if What becomes clear during the investigation, do not proceed directly to implementation. Have the human approve the conclusion, and create an implementation task

### 1. Settle the Investigation's Direction (Human Approves)

1. Generate task.yaml and the document from the templates
1. Write Background / What / Why / Scope / Out of Scope
    - Background: what is already known and the history, as premises for the investigation
    - What: what to investigate and organize
      - Questions: the questions the investigation should answer. Write them concretely as a bullet list (e.g. "Which job is hitting X's rate limit?", "Should we choose option A or option B?")
      - Done When: the condition for ending the investigation (e.g. "All Questions are answered and one option to implement has been chosen")
    - Why: why the investigation is needed. What is undecided, and what will be decided from the investigation's conclusion
    - Scope / Out of Scope: what is and is not investigated
1. Have an agent review it, and repeat until it converges (see "Review Rules")
1. Get the human's approval

### 2. Investigate (AI Runs)

1. Investigate. Record what you looked into, what you tried, and the sources (URLs, commands and their output, etc.) in details.md as primary information
1. In Findings, summarize what was learned for each Question. Show the evidence with links to details.md or the sources
1. In Conclusion, write the investigation's conclusion (what to do and not do). If there are multiple options, write a comparison and the recommended option
1. In Next Tasks, write candidate tasks to create from the conclusion. Write each in enough detail to convey an outline of its What / Why / Scope
1. Have an agent review it, and repeat until it converges. Have it check that the Questions are answered, that the Findings are based on evidence, and that the Conclusion follows from the Findings

If the approved Questions / Scope cannot produce an answer, or the investigation's direction needs to change, do not decide on your own; ask the human, update the document, then proceed.

### 3. Decide on the Conclusion (Human Approves)

1. Get the human's approval of Findings / Conclusion / Next Tasks
1. Create a new task for each approved Next Task (`type: implementation`, or `type: investigation` if further investigation is needed)
    - In the new task's Background, write the investigation task's conclusion and a link to the investigation task's document
    - Set both `derived_from` / `derived_tasks` in task.yaml
    - New tasks start from step 1 of Steps. Write the overview based on the investigation's conclusion and get the human's approval
1. Set the investigation task's `status` to `done`

## Review Rules

- Have a subagent with a fresh context do the review, and pass it only the documents (the pull request, for pull request reviews). Passing the writer's context drags the reviewer toward the writer's conclusions
- Have the reviewer report only comments that need fixing in light of the document's purpose and scope. Do not have it report matters of taste or nits
- In reviews of the overview and Behaviour, also have it check that they follow "Writing the Overview" (premises are written, they are not written in terms of internal implementation)
- Write out-of-scope comments in Follow-ups
- Finish when no comments that need fixing remain. There is no upper limit on the number of rounds
- If the same point goes back and forth, stop the loop and ask the human

## PR Explanation: Purpose and Contents

Purpose:

- A document to assist human review

What to write:

How to write it depends on the pull request, but code changes generally include the following.

- At the top, write a short summary of the changes per module unit (Package in Go)
- Structure the body around the order in which the code is read (the execution flow), and in that order describe the role, callers, and changes of each changed function, type, etc.

The following is an example for a change to code written in Go.

- At the top, write a short summary of the changes per Package
- Structure the body around the order in which the code is read (the execution flow), and in that order describe what each changed function does, where it is called from, and what changed

What to write in every pull request:

- Places you want the human to look at. In step 3 the AI decides autonomously, so let the human verify those decisions
  - Places where the implementation differs from the Implementation Plan, and why
  - Places with side effects or risks that you especially want checked
  - What tests confirm and what they do not

How to write:

- Only refer to Behaviour for the specification and Implementation Plan for the implementation approach; do not duplicate them. Focus on explaining the code
- Point to code locations with GitHub links pinned to a commit SHA (`https://github.com/<owner>/<repo>/blob/<commit SHA>/<path>#L<start>-L<end>`), so the links do not drift when the pull request is updated
- Attach the corresponding code snippet to each item of the explanation

## PR Explanation Format

Write the PR Explanation in Markdown in `tasks/<task id>/pr-explanation.md`. Order each step as "explanation → link → code snippet", so reading from top to bottom follows the order in which the code is read.

````markdown
# PR Explanation: <pull request title>

<pull request URL> head: <commit SHA>

## TL;DR

<a few lines>

## Summary of Changes

| Module | Changes |
|--------|---------|
| pkg/foo | ... |

## Places to Look At

- ⚠️ <something that needs a decision>: <details>
- <something to check>: <details>

## Tests

- Confirmed: ...
- Not confirmed: ...

## Code Walkthrough

### 1. <step heading> (pkg/foo)

<the role of this function, where it is called from, what changed>

[pkg/foo/foo.go#L40-L44](https://github.com/<owner>/<repo>/blob/<commit SHA>/pkg/foo/foo.go#L40-L44)

```diff
 func Foo() error {
-	return bar()
+	if err := bar(); err != nil {
+		return fmt.Errorf("bar: %w", err)
+	}
+	return nil
 }
```

### 2. ...
````

- Limit snippets to the range needed for the explanation. Do not paste whole files or whole hunks
- Use `diff` to show changes, and a code block in the relevant language to show new code or surrounding context
- In the PR Explanation section of `<task id>.md`, write only the TL;DR and a link to `pr-explanation.md`; do not write the same content twice
