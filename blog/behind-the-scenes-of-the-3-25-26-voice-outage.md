<p>
 <sup>
  This article is a collaborative piece by
 </sup>
 <strong>
  <sup>
   Bo Ingram, Senior Staff Engineer on Realtime Infrastructure
  </sup>
 </strong>
 <sup>
  , and
 </sup>
 <strong>
  <sup>
   Stephen Birarda, Senior Staff Engineer on Audio/Video infrastructure
  </sup>
 </strong>
 <sup>
  .
 </sup>
</p>
<p>
 The sad trombone haunts our dreams. Womp, womp, womp, woOoOoOoOmp. Womp, womp, womp, woOoOoOoOmp. Womp, womp, womp, woOoOoOoOmp. A cascading outage manifests in many ways: processes crashing, users reconnecting. As an on-call engineer, you often see it firsthand when the alert notifications reach your phone.
</p>
<p>
 On March 25th, voice and video on Discord suffered major degradation beginning at 12:13 PDT until 15:30 PDT. During this time, users were mostly unable to start or join calls, seeing an “Awaiting Endpoint” message in their call status.
</p>
<p>
 As part of a routine infrastructure change, a configuration update accidentally caused a large portion of Discord’s session management servers to shut down simultaneously. Sessions are the heartbeat of Discord’s real-time infrastructure — every connected device maintains one, and they coordinate nearly everything you see and hear in the app. Losing 17% of them at once sent a cascade of impacts through several downstream systems, ultimately overwhelming a service responsible for routing voice and video calls to the right servers around the world.
</p>
<p>
 Since the incident, we’ve taken time to analyze our systems, understand why they degraded in the face of the cascading load from our session outage, and determine how we can leverage our experience from the outage to level up our infrastructure. In a distributed system, sudden load is a dangerous proposition. It hurtles through old bottlenecks and seeks out new ones. In this post, we’ll peek behind the curtain and see how one seemingly innocuous change overwhelmed a system multiple hops away and how our not-fun afternoon helped us improve Discord.
</p>