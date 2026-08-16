<p>
 Last year, we introduced the
 <a href="https://discord.com/blog/meet-dave-e2ee-for-audio-video">
  DAVE protocol
 </a>
 as our solution to bring end-to-end encryption ("E2EE" for short) to Discord's audio and video calls. Since then, DAVE has been providing E2EE for tens of millions of calls on Discord
 <em>
  every single day
 </em>
 . Today, we're excited to announce that we're bringing DAVE support to all our remaining platforms, including browsers, consoles and our Social SDK.
</p>
<p>
 <strong>
  Starting March 1st 2026, clients and apps without DAVE support will no longer be able to participate in Discord calls.
 </strong>
 This will complete our transition from last year’s experimental rollout to making DAVE the standard for Discord voice and video calls.
</p>
<p>
 In this article, we'll explore the technical challenges and tradeoffs we encountered while integrating DAVE with web browsers, from WebAssembly performance considerations to Web Worker architecture decisions. We'll also share more about our timeline for deprecating non-E2EE calls and what you may need to do to make sure you or your application can still connect to voice channels come March 1st 2026.
</p>