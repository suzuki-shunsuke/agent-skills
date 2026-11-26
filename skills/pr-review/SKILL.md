---
name: pr-review
description: When asked to review a pull request created by someone else, generates documents explaining the pull request's overview, specification, and code so that a human without its context can review it, and presents an agent's review results alongside them. Use when asked to review or understand a pull request. Do not use for pull requests you created and manage with dev-flow.
---

## Principles

- The goal is to support human review. A human without the pull request's context should be able to judge and comment appropriately just by reading the documents
- The agent does not make review decisions on the human's behalf. Present the agent's review results as material for the human's judgment, and do not comment on, approve, or request changes on the pull request without the human's approval
- Distinguish facts read from the pull request from the agent's guesses. Mark anything written from a guess as a guess, and turn it into a question for the pull request author (Questions for Author)

## Starting the Flow

Start this flow when a human asks you to review or understand a pull request, even if the skill is not explicitly invoked.

Pull requests created and managed with dev-flow (pull requests with a corresponding task in tasks/) are out of scope. For those, follow the dev-flow flow.

1. Look for documents corresponding to the request in `reviews/<owner>/<repo>/<pr number>/`
1. If there are none, start from step 1 of Steps
1. If there are, compare the Reviewed Head recorded in the documents with the pull request's current head. If the pull request has been updated, follow "When the Pull Request Is Updated"; otherwise resume from step 5 of Steps

For each review, open a new pane in herdr, start Claude Code there, and proceed.

## Document Layout

```
reviews/
  <owner>/<repo>/<pr number>/
    review.md
    details.md
    pr-explanation.md
```

- `review.md`: the main document, generated from templates/review.md. It summarizes the overview, specification, and review results, and is what the human reads first
- `details.md`: the record of primary information and decisions. Write the collected information (commands and the gist of their output, URLs of referenced issues, related pull requests, Slack threads, etc.), the evidence behind guesses, and for each finding of the agent's review whether it was adopted or rejected and why. Keep it separate from review.md because it tends to grow large
- `pr-explanation.md`: the PR Explanation (see "PR Explanation")

## Steps

### 1. Collect Information

1. Get the pull request's information
    - `gh pr view <number> -R <owner>/<repo> --json title,body,author,baseRefName,headRefName,headRefOid,files,additions,deletions,labels,closingIssuesReferences,url`
    - `gh pr diff <number> -R <owner>/<repo>`
    - Existing review comments and conversations (`gh pr view --comments`, `gh api repos/<owner>/<repo>/pulls/<number>/comments`)
    - CI results (`gh pr checks`)
1. Collect the intent and history of the change from the pull request's description, linked issues, and related pull requests
1. The diff alone does not show callers or surrounding context, so check out the pull request's head with git worktree and read the code (see the git-worktree skill)
1. Base everything written from here on on the head SHA at this point. Record it as Reviewed Head in review.md

Record the collected information and its sources in details.md.

### 2. Write the Overview and Specification

Generate the document from templates/review.md and write Background / What / Why / Scope / Out of Scope / Behaviour.

#### How to Write the Overview

The overview lets a reader judge the problem the pull request tries to solve and its direction without reading the code.

- Background: write what the reader needs to know as a premise. What the related features or commands do (e.g. what `aqua vacuum` is, what `--init` is for), the history so far, and so on. Make sure the human does not end up asking "wait, what was this again?"
- What / Why: write in terms of behaviour as seen by users. Do not write about internal implementation such as function or type names. If needed, write those in the PR Explanation or details.md
  - When the change itself is about internal implementation, such as refactoring, it is fine to talk about internal implementation. Even then, make sure the reader can grasp the premise from Background
- For changes that alter behaviour, write Before / After in What to contrast what changes and how (e.g. the current result and the result after the change when running the same command)
- Where possible, write the current problem in Why as bug reproduction steps to make it easy to picture
  - How To Reproduce: the steps (example configuration files and commands)
  - Expected Behaviour: the expected behaviour
  - Actual Behaviour: the actual behaviour
  - You may omit these for changes they do not fit, such as new features or improvements
- Write Scope / Out of Scope / Behaviour in terms of behaviour as much as possible too. Put function names and the like in the PR Explanation

For pull requests by others, also follow these rules.

- Do not copy the pull request's description as is. Fill in premises the description does not state (what the related features do, the history) so that someone without the context can read it
- Explicitly note places where the description and the implementation disagree, as disagreements
- In Scope, write what the pull request actually changes; in Out of Scope, write what the pull request intentionally does not change (if the description or issue says so)
- If the pull request includes changes outside its purpose (incidental refactoring, changes to unrelated files, etc.), write them in "Out-of-Scope Changes"
- Mark anything written from a guess with `(guess)` and write the evidence in details.md. Write anything you cannot confirm in Questions for Author

### 3. Write the PR Explanation

Write pr-explanation.md following "PR Explanation". In the PR Explanation section of review.md, write only the TL;DR and a link to pr-explanation.md.

### 4. Have Agents Review

1. Pull request review: have a subagent with a fresh context review the pull request, given only the pull request (URL, diff, checked-out code). Do not pass the documents or your own interpretation. Passing the writer's context drags it toward the writer's conclusions
    - Aspects: correctness (bugs, boundary conditions, error handling), whether the change is sufficient for the pull request's purpose and contains nothing extra, whether it breaks compatibility, security, and the validity of tests
    - Have it report only findings that need fixing and questions to confirm with the pull request author. Do not have it report matters of taste or nits
1. Verify the findings: for each finding, read the code to check whether it really holds. Reject findings that do not hold and write the reason in details.md
1. Write the findings that hold in Review Findings in review.md (see "How to Write Review Findings")
1. Document review: give review.md, pr-explanation.md, and the pull request to another subagent with a fresh context, and have it check whether the documents explain the pull request correctly
    - Statements that differ from the facts, important changes in the pull request that are not explained, and guesses not marked with `(guess)`
    - Whether the documents follow "How to Write the Overview" (whether premises are written, whether they avoid talking in terms of internal implementation)
1. Reflect the findings on the documents

Run the pull request review and the document review once each. Do not repeat them until they converge as in dev-flow. Reviewing does not change the pull request's code, so repeating only increases the variance of the findings. If, after reflecting the findings, there are places in the documents whose correctness you are not confident about, tell the human when handing over.

#### How to Write Review Findings

For each finding, write the following.

- Severity
  - `must`: should be fixed before merging (bugs, data corruption, security, breaking compatibility, etc.)
  - `should`: better fixed, but the merge decision is left to the human
  - `question`: the intent cannot be read and you want to confirm with the pull request author
- Location: a GitHub link pinned to a commit SHA
- Problem: what is wrong
- Evidence: the concrete input or state that causes the problem, and its result
- Suggestion: a proposed fix (if any)

Write improvement ideas outside the pull request's purpose in Follow-ups, not in Review Findings.

### 5. Hand Over to the Human

1. Open the documents with `mo` (`mo reviews/<owner>/<repo>/<pr number>/review.md reviews/<owner>/<repo>/<pr number>/pr-explanation.md`)
1. The human reads the documents and asks questions in conversation with the agent. The agent answers and reflects the answers in the documents if needed (mo reloads automatically on save)
1. The human decides which Review Findings to comment on the pull request, and whether to Approve, Request changes, or Comment

### 6. Post Comments (the Human Approves)

1. Draft review comments from the findings the human chose, and show them to the human. The pull request author reads them, so do not reuse the documents' internal notation (`(guess)`, severity labels, etc.) as is; write prose that conveys the evidence and suggestion.
1. Post them only after getting the human's approval (see the review-comment skill). Approve or Request changes only when the human explicitly instructs it
1. Record the URLs of the posted comments in details.md and update the status of the Review Findings

## When the Pull Request Is Updated

1. Check the diff from the Reviewed Head to the new head (`git diff <reviewed head>..<new head>` or GitHub's compare)
1. Update review.md and pr-explanation.md according to the diff. Repoint code links to the new head's SHA
1. Have an agent review the added diff under the same rules as step 4 of Steps. Also check whether existing Review Findings have been resolved, and update their status
1. Update Reviewed Head to the new head, and record what changed in details.md
1. Resume from step 5 of Steps

## PR Explanation

Purpose:

- Assist the human who reads the code in reviewing it. While review.md explains "what the pull request does", the PR Explanation explains "how the code works"

What to write:

How to write it depends on the pull request, but code changes generally include the following.

- At the top, write a short summary of the changes per module unit (Package in Go)
- Structure the body around the order in which the code is read (the execution flow), and in that order describe the role, callers, and changes of each changed function, type, etc.

What to write in every pull request:

- Places to look at
  - Links to the `must` / `should` Review Findings
  - Places where the implementation disagrees with the pull request's description or issue
  - Places that are not findings but that the reviewer should understand (changes with side effects or a wide impact, behaviour that is hard to follow)
- Tests: what the tests in the pull request confirm and what they do not, and the CI results

How to write:

- Only refer to Behaviour in review.md for the specification; do not duplicate it. Focus on explaining the code
- Point to code locations with GitHub links pinned to a commit SHA (Reviewed Head) (`https://github.com/<owner>/<repo>/blob/<commit SHA>/<path>#L<start>-L<end>`), so the links do not drift when the pull request is updated
- Attach the corresponding code snippet to each item of the explanation

### Format

Write it in Markdown in `reviews/<owner>/<repo>/<pr number>/pr-explanation.md`. Order each step as "explanation → link → code snippet", so reading from top to bottom follows the order in which the code is read.

````markdown
# PR Explanation: <pull request title>

<pull request URL> · head: <commit SHA>

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
- CI: ...

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

For pull requests whose diff is too long to read comfortably in Markdown, you may generate HTML with the code on the left and the explanation on the right. See references/pr-explanation-html.md for the steps.
