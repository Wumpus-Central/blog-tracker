<p>
 At Discord, we faced a challenge that would make most data teams flinch: scaling
 <a href="https://www.getdbt.com/">
  dbt
 </a>
 to process petabytes of data while supporting 100+ developers simultaneously working across 2,500+ models. What started as a simple implementation quickly hit critical limitations to accommodate millions of concurrent users generating petabytes of data.
</p>
<p>
 dbt (data build tool) is a command-line tool that transforms data in your warehouse and brings software engineering principles to the world of SQL. Originally developed by
 <a href="https://www.getdbt.com/blog/welcome-to-fishtown-analytics">
  Fishtown Analytics
 </a>
 , a Philadelphia-based consulting firm, dbt has grown from humble beginnings to become widely adopted by data practitioners worldwide, leading to the company's rebranding as dbt Labs to reflect the tool's prominence.
</p>
<p>
 Our journey with dbt began several years ago when we were evaluating solutions that could handle our rapidly growing data needs while maintaining the flexibility and transparency that engineers at Discord value. We chose dbt primarily because of its open-source nature, which aligns with Discord's engineering philosophy of leveraging and contributing to the open-source community whenever possible.
</p>
<p>
 dbt offers several key features that made it attractive for our data transformation needs:
</p>
<ul role="list">
 <li>
  Seamless integration across other tools in our data stack (see our previous
  <a href="https://discord.com/blog/how-discord-uses-open-source-tools-for-scalable-data-orchestration-transformation">
   blog post
  </a>
  about our orchestrator Dagster!)
 </li>
 <li>
  Developer-friendly experience for data transformation
 </li>
 <li>
  Modular design that promotes code reusability and maintainability
 </li>
 <li>
  Comprehensive testing framework to ensure robust data quality
 </li>
</ul>
<p>
 However, our initial implementation of dbt began to buckle under the scale of Discord. We encountered frequent re-compilation of the entire dbt project, amounting to painful 20+ minute waits. The default incremental materialization strategy wasn't optimized for our data volumes. Developers found themselves overwriting each other's test tables, creating confusion and wasted effort. Without addressing these scaling challenges, our ability to deliver timely data insights would have been severely compromised.
</p>
<p>
 To scale beyond dbt's standard capabilities, we've implemented custom solutions that extend its core functionality. We built a state-of-the-art dbt system better-suited for a company of Discord’s size that enhances developer productivity, prevents breaking changes, and streamlines complex calculations. The customizations we've made, which we'll detail throughout this post, have allowed us to overcome these challenges and build a robust, scalable data transformation platform that serves as the backbone of our analytics infrastructure.
</p>
<p>
 This isn't just another "how we use dbt" story — it's a blueprint for extending dbt to handle truly massive scale. We’re transforming painful compile times into rapid development cycles while ensuring robust data quality, and automating complex backfills that would otherwise require extensive manual intervention.
</p>
<p>
 While we use Google BigQuery as our cloud provider, our solution is largely provider-agnostic and can be applied to other cloud platforms.
</p>