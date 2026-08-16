<p>
 You've been asked to stand up a brand-new database cluster — a full replica of production, running real traffic, so you can validate a new release before it touches actual data.
</p>
<p>
 You're looking at the next day and a half, and it’s lookin’ stacked: provisioning and configuring dozens of nodes, joining them to the cluster one at a time, validating replication, wiring up dual-write pipelines, and babysitting the whole thing because
 <em>
  any
 </em>
 mistake on the ninth step means starting the whole thing over from scratch. While grinding through the whole process, you start to daydream: what if this whole ordeal took less than two hours?
</p>
<p>
 We found ourselves in exactly this situation. This is the story of how we got ourselves into this mess and how we made our way out of it.
</p>