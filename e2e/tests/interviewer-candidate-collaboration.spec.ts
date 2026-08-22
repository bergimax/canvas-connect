import { test, expect, type Browser, type Page } from "@playwright/test";

// Email is prefilled by the login form itself — see frontend/src/routes/login.tsx.
const INTERVIEWER_PASSWORD = "password123";

async function loginAsInterviewer(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Password").fill(INTERVIEWER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/sessions");
}

async function createSession(page: Page, title: string): Promise<void> {
  await page.getByRole("button", { name: "New session" }).click();
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Prompt").fill("Design a URL shortener for a Playwright E2E run.");
  await page.getByRole("button", { name: "Create" }).click();
  // The create dialog closes itself on success — its disappearance is proof
  // the session was actually created, not just that the request was sent.
  await expect(page.getByRole("dialog")).toBeHidden();
}

async function openSession(page: Page, title: string): Promise<void> {
  await page.getByText(title, { exact: true }).click();
  await page.waitForURL("**/sessions/*");
}

/** Opens the guest-link dialog, mints a new candidate link, and returns its URL. */
async function shareJoinLink(page: Page): Promise<string> {
  await page.getByRole("button", { name: "Guest links" }).click();
  await page.getByRole("button", { name: "New candidate link" }).click();

  const linkLocator = page.locator("span.font-mono", { hasText: "/join/" });
  await expect(linkLocator).toBeVisible();
  const url = (await linkLocator.textContent())?.trim();
  if (!url) throw new Error("Guest link URL was empty");

  await page.keyboard.press("Escape");
  return url;
}

async function joinAsCandidate(browser: Browser, joinUrl: string, displayName: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(joinUrl);

  await expect(page.getByText("Join interview", { exact: true })).toBeVisible();
  await page.getByLabel("Your name").fill(displayName);
  await page.getByRole("button", { name: "Join" }).click();
  await page.waitForURL("**/sessions/*");
  return page;
}

const canvasSurface = (page: Page) =>
  page.locator('svg[aria-label="Collaborative system design canvas"]');

test("candidate's canvas edit becomes visible to the interviewer", async ({ browser }) => {
  // Session 1: the interviewer, in their own isolated browser context —
  // separate localStorage from the candidate's, exactly like two different
  // people in two different browsers.
  const interviewerContext = await browser.newContext();
  const interviewerPage = await interviewerContext.newPage();

  const sessionTitle = `Playwright E2E ${Date.now()}`;

  await test.step("1. Log in as the interviewer", async () => {
    await loginAsInterviewer(interviewerPage);
  });

  await test.step("2. Create an interview session", async () => {
    await createSession(interviewerPage, sessionTitle);
    await openSession(interviewerPage, sessionTitle);
  });

  let joinUrl = "";
  await test.step("3. Share the join link", async () => {
    joinUrl = await shareJoinLink(interviewerPage);
    expect(joinUrl).toContain("/join/");
  });

  // Session 2: the candidate, joining from a separate client.
  let candidatePage: Page;
  await test.step("4. Join from a separate client as the candidate", async () => {
    candidatePage = await joinAsCandidate(browser, joinUrl, "Ada Candidate");
    await expect(canvasSurface(candidatePage)).toBeVisible();
  });

  await test.step("5. Change the canvas as the candidate", async () => {
    await candidatePage.getByTitle("Add Server").click();
    await expect(canvasSurface(candidatePage).getByText("Server", { exact: true })).toBeVisible();
  });

  await test.step("6. Verify the interviewer sees the change", async () => {
    // No live push between clients (see frontend/src/lib/realtime.ts) — the
    // interviewer's canvas only catches up via its polling refetch, so this
    // relies on playwright.config.ts's extended expect timeout, not a fixed
    // sleep.
    await expect(canvasSurface(interviewerPage).getByText("Server", { exact: true })).toBeVisible();
  });
});
