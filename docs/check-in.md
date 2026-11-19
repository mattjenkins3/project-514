# Interactive browser check-in

Open [the form file](../check-in/index.html) in a browser. It has tap choices for outcome, recovery and discomfort, an effort slider, and fields tailored to climbing or running. Rest days do not ask for workout metrics. The form starts on yesterday's Denver date.

Select **Copy check-in for ChatGPT**, then paste and send the result in the existing **Project 5.14 | Morning Coach** conversation. The coach writes your plan after receiving that message. **Skip check-in** copies a request for a conservative plan. You can open the file offline. If your browser blocks clipboard access to local files, it selects the generated text for manual copying.

## Optional free URL

To open the form from a scheduled ChatGPT message, publish just the `check-in/` folder with [Cloudflare Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/). The page is public, but it collects no accounts, analytics, or data. All answers stay in the browser until you paste them into ChatGPT.

1. In the Cloudflare dashboard, open **Workers & Pages → Create → Pages → Drag and drop your files**.
2. Name the Pages project and upload the `check-in/` folder with `index.html` at its root. Use the free Pages option.
3. Open the assigned `pages.dev` URL and verify the form loads. Put that URL in `CHECKIN_URL` when you paste the [task prompt](task-prompt.md) into ChatGPT **Scheduled**.

Your repository can remain private. This upload does not need GitHub integration, a paid server, a database, or a ChatGPT password.
