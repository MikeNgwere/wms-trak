"""
Research Paper — Chapters 1-3 (Introduction, Literature Review,
Methodology), written for the project, natively inside the app.
"""
import streamlit as st

from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="Research Paper — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("Research Paper — Chapters 1–3")
st.caption("Development of a Digital Reconciliation and Expiry Monitoring System for State Warehouse Compliance at ZIMRA")

chapter = st.radio("Jump to:", ["Chapter 1: Introduction", "Chapter 2: Literature Review", "Chapter 3: Methodology"], horizontal=True)
st.divider()

if chapter == "Chapter 1: Introduction":
    st.header("CHAPTER 1: INTRODUCTION")

    st.subheader("1.1 Background of the Study")
    st.write(
        "Any officer who has manned the Bonds and Exports desk, or spent a shift at the State Warehouse, "
        "will recognise the process this study is concerned with. Goods that cannot be entered on arrival "
        "end up in our custody under section 39 of the Customs and Excise Act [Chapter 23:02] — logged in "
        "the RIH register while duty, penalties, and warehouse rent remain outstanding. Others land with us "
        "through a Notice of Seizure under section 193, held while the importer's three-month window to "
        "contest the seizure runs its course. Both processes are familiar to every officer who has worked a "
        "border station, and both currently depend on the same tool: a paper register, filled in by hand, "
        "cross-checked by memory and periodic physical stock-taking."
    )
    st.write(
        "ASYCUDA World has, over the years, become second nature for processing declarations — but it was "
        "never built to answer the question every warehouse officer eventually has to ask: how long has this "
        "consignment actually been sitting here, and are we still within the law to hold it? That question is "
        "currently answered by walking to the shelf, finding the file, and doing the arithmetic by hand. At "
        "Forbes Border Post, as at most stations, this means the sixty-day RIH clock and the ninety-day NOS "
        "appeal window are tracked the same way they were a decade ago — manually, and only as often as "
        "someone remembers to check."
    )
    st.write(
        "The consequence is one every officer has seen play out: goods that quietly cross the sixty-day line "
        "without anyone noticing until the next physical audit catches it. By then, duty that should have "
        "been assessed weeks earlier is still sitting uncollected, and a seizure whose appeal window lapsed "
        "months ago is still occupying warehouse space because nobody flagged it for disposal. This is not a "
        "failure of any individual officer's diligence — it is what happens when a compliance deadline lives "
        "only in a paper file and nowhere else."
    )
    st.write(
        "This research paper sets out the development of WMS-Trak — a digital tool built to sit alongside "
        "ASYCUDA World, not to replace it, and to do the one thing the paper register cannot: watch every RIH "
        "and NOS entry continuously, flag it the moment it crosses its legal deadline, and carry it through a "
        "proper, auditable approval chain to its final disposition — release, forfeiture, destruction, or "
        "e-auction."
    )

    st.subheader("1.2 Statement of the Problem")
    st.write(
        "The core difficulty is not that officers are careless with the paper register — it is that the "
        "register itself has no way of raising an alarm. A file sits in a drawer whether it is three days old "
        "or three months overdue; the register cannot tell the difference on its own. Detection of an "
        "overstayed RIH or a lapsed NOS appeal window therefore depends entirely on someone going and looking "
        "— and in a busy station handling multiple consignments across several warehouses, that check happens "
        "only as often as staffing and workload allow, which in practice means periodic physical audits rather "
        "than continuous monitoring."
    )
    st.write(
        "The downstream effect touches revenue directly. Duty, penalties, and warehouse rent that should be "
        "assessed the moment a bond period lapses often go uncollected until an audit catches the file. On the "
        "seizure side, goods whose appeal window has closed without challenge should move promptly toward "
        "disposal — yet without a system flagging that milestone, they can sit in the warehouse indefinitely, "
        "tying up space and leaving the disposal decision undocumented until someone happens to revisit the "
        "file. Supervisors and station managers, meanwhile, have no consolidated view of how many RIH and NOS "
        "entries are approaching their deadlines across the warehouses under their watch — that picture "
        "currently exists only in whoever's memory holds the most files."
    )
    st.write(
        "The problem this study set out to solve, in language any officer at the desk would recognise, is "
        "this: how do we make the sixty-day RIH clock and the ninety-day NOS clock ring on their own, without "
        "waiting for the next audit to notice — and how do we make sure that once a disposition decision is "
        "made, it is signed off properly and recorded for good, the same way a well-run bond file should be?"
    )

    st.subheader("1.3 Research Objectives")
    st.markdown("**1.3.1 Main Objective**")
    st.write(
        "To design, develop, and pilot-test a digital Warehouse Management System (WMS-Trak) that gives every "
        "RIH and NOS entry a running clock against its correct statutory deadline, and carries it through a "
        "proper Officer–Supervisor–Manager sign-off chain to final disposition — operating alongside ASYCUDA "
        "World, not in place of it."
    )
    st.markdown("**1.3.2 Specific Objectives**")
    st.markdown(
        "1. To confirm, from the Act, the Regulations, and ZIMRA's own procedures, exactly how many days an "
        "RIH entry and an NOS appeal are legally entitled to run — and to build those figures into the system "
        "as configurable rules rather than fixed code.\n"
        "2. To build a capture screen that records everything an officer would normally write on an RIH or "
        "NOS file — importer detail, goods description, and vehicle detail where relevant — without missing a "
        "field the paper register would have caught.\n"
        "3. To give officers a live, at-a-glance view of warehouse and vehicle-pound occupancy at their "
        "station, including the ability to mark a facility full.\n"
        "4. To build a proper sign-off chain — Officer requests, Supervisor reviews, Manager gives final "
        "approval — covering all four ways a detained item can leave the warehouse: released to its owner, "
        "forfeited to the State, destroyed, or sold by e-auction.\n"
        "5. To capture the revenue side properly at the point of release — duty, additional duty, and rent "
        "calculated automatically from the number of days the item actually sat in the warehouse.\n"
        "6. To put the finished system in front of real officers, and find out — through a structured "
        "questionnaire and proper statistical testing — whether it genuinely beats the paper register, or "
        "just looks like it does."
    )

    st.subheader("1.4 Research Questions")
    st.write("Three questions sit behind this study, each explored through five questionnaire items put directly to pilot officers:")
    st.markdown(
        "- **RQ1:** What did the manual, paper-based process actually get wrong, in the experience of officers who used it every day?\n"
        "- **RQ2:** Does WMS-Trak genuinely fix those problems, or does it just move them somewhere else?\n"
        "- **RQ3:** Is the system something an officer would actually want to use, and does it show any real benefit to compliance and revenue outcomes?"
    )

    st.subheader("1.5 Significance of the Study")
    st.markdown(
        "**To ZIMRA:** a working tool that catches overstayed RIH goods and lapsed NOS appeals before the "
        "next audit does, closing a revenue gap that has existed for as long as the paper register has been "
        "the only line of defence — at a fraction of the cost and disruption of touching ASYCUDA World itself."
    )
    st.markdown(
        "**To officers and supervisors at the desk:** a single screen that shows, at any moment, which files "
        "are approaching their deadline and which warehouses are near capacity — instead of that picture "
        "living only in whoever last checked the files."
    )
    st.markdown(
        "**To the research group:** the chance to take a problem every one of us has seen firsthand on "
        "rotation, and turn it into something that actually works — sharpening our grounding in the Act "
        "itself, in systems design, and in what it takes to build something an officer would trust enough to "
        "use daily."
    )
    st.markdown(
        "**To ZIMRA more broadly and other revenue authorities:** a documented, working example of what a "
        "lightweight digital layer can achieve without requiring a full ASYCUDA World overhaul."
    )

    st.subheader("1.6 Scope and Delimitations")
    st.write(
        "This study is confined to RIH and NOS goods, piloted at Forbes Border Post. Removal in Bond and "
        "Removal in Transit were part of our original scope, but an early review found ASYCUDA World already "
        "tracks those movements adequately — it was the state warehouse and seizure side, still running on "
        "paper, that genuinely needed the work. WMS-Trak is built to sit alongside ASYCUDA World as a control "
        "layer, not to touch or replace it."
    )

    st.subheader("1.7 Limitations")
    st.markdown(
        "- The pilot covers one station; a station with different goods composition, staffing, or volume may see different results.\n"
        "- Questionnaire data collection was still underway as this chapter was written, so the sample available for the statistical analysis may still be modest.\n"
        "- Testing used a mix of live and simulated data, given the sensitivity of real warehouse records during a training placement; a full rollout would need a proper data-migration exercise first."
    )

    st.subheader("1.8 Definition of Key Terms")
    st.markdown(
        "- **RIH:** goods conveyed to a State Warehouse under section 39 of the Act because entry was not made in time, held pending payment of duty, penalties, and warehouse rent.\n"
        "- **NOS:** the formal notice issued when goods are seized under section 193, opening a statutory window for the importer to contest the seizure before it becomes final.\n"
        "- **Bond period:** the number of days the law allows before duty becomes payable or further action is required.\n"
        "- **ASYCUDA World:** ZIMRA's primary system for processing customs declarations.\n"
        "- **Disposition:** what ultimately happens to a detained item — release to the owner, forfeiture to the State, destruction, or sale by e-auction."
    )

elif chapter == "Chapter 2: Literature Review":
    st.header("CHAPTER 2: LITERATURE REVIEW")

    st.subheader("2.1 Introduction")
    st.write(
        "This chapter walks through the legal ground this study stands on, the weaknesses of the "
        "paper-register approach that every officer working the state warehouse desk will recognise, and "
        "where a lightweight digital tool fits alongside a platform like ASYCUDA World rather than in "
        "competition with it."
    )

    st.subheader("2.2 Legal and Regulatory Framework")
    st.write(
        "Every business rule in WMS-Trak traces back to a specific provision, not a guess. Section 39(1)(b) "
        "of the Customs and Excise Act [Chapter 23:02] gives an importer ten days from importation to enter "
        "goods sitting in a transit shed, failing which they are treated as abandoned and moved to the State "
        "Warehouse. From there, section 39(2) gives a further period — currently sixty days, not the three "
        "months many of us grew up hearing quoted on the floor — to enter the goods and settle duty, "
        "penalties, and rent. That sixty-day figure has been law since the Finance (No. 3) Act 10 of 2009 "
        "took effect on 8 January 2010, reducing it down from the original three months. If that period "
        "lapses, section 39(3) allows the Commissioner to sell by public auction, with at least a month's "
        "Gazette notice, or — for goods with no commercial value, or that are dangerous or perishable — to "
        "sell out of hand, destroy, or appropriate them."
    )
    st.write(
        "Section 193 governs seizures. Once a Notice of Seizure is issued, subsection (12) gives the person "
        "from whom the goods were taken three months to institute proceedings to get them back. If that "
        "window closes without a challenge, subsection (13) is unambiguous: the goods vest in the State, with "
        "no compensation, and may be sold, destroyed, or appropriated. It is worth stating plainly, because "
        "it is easy to blur the two in daily practice: the RIH clock and the NOS clock are governed by "
        "different sections of the Act, run for different lengths of time, and must never be treated as the "
        "same deadline. Getting this distinction wrong in a manual file is an easy mistake to make; getting "
        "it wrong in a system that is meant to enforce the law automatically would be far worse — which is "
        "exactly why this distinction was checked against the Act directly rather than against institutional "
        "memory before a single line of the system was written."
    )
    st.write(
        "ZIMRA's own Consolidated CEP Procedures Summary (CEP0114, Treatment of Goods in Transit) backs up "
        "the ten-day transit-shed figure and confirms that unresolved transit-shed goods become RIH, disposed "
        "of by Rummage Sale once the sixty-day period is spent. One finding worth flagging to any officer "
        "reading this: in the course of confirming these figures, we found that day-to-day practice at "
        "station level still sometimes cites the old three-month RIH figure — a decade after the law changed. "
        "That gap between what the Act says and what gets repeated on the floor is itself a small but telling "
        "illustration of exactly the kind of compliance risk this study is trying to close."
    )

    st.subheader("2.3 What the Paper Register Actually Gets Wrong")
    st.write(
        "None of this will surprise an officer who has worked the desk, but it is worth setting down "
        "plainly: a paper register cannot flag anything on its own. It cannot tell you a file is overdue "
        "unless someone opens it and does the arithmetic. It cannot reconcile itself against what is "
        "physically sitting on the warehouse floor. It has no memory of which officer handled which step of "
        "a disposal, beyond whatever was written down at the time — and if that entry was skipped in a busy "
        "shift, that piece of the trail is simply gone. These are not failures of any individual officer's "
        "care; they are the built-in limits of a system that depends entirely on someone remembering to check."
    )

    st.subheader("2.4 Where a Digital Layer Fits Alongside ASYCUDA World")
    st.write(
        "ASYCUDA World does what it was built to do extremely well — processing declarations and tracking "
        "the movement of goods across a border. It was never designed to sit and watch a physical warehouse "
        "shelf, counting days against a bond period or an appeal window. That is a genuinely different job, "
        "and trying to bolt it onto a platform built for something else is neither quick nor necessary. What "
        "is needed instead is a smaller, purpose-built tool that does exactly this one job well, and hands "
        "off to ASYCUDA World for everything it already does properly. WMS-Trak was built with that division "
        "of labour deliberately in mind — it does not touch declaration processing, and it does not try to."
    )

    st.subheader("2.5 Conceptual Framework")
    st.write(
        "The problem breaks down into four stages that map directly onto how an officer already thinks "
        "about a file: capture (an officer records the RIH or NOS entry, with everything the paper form "
        "would have asked for); tracking (the system counts the days automatically against the correct legal "
        "threshold, and against warehouse occupancy); approval (a request moves through Officer, Supervisor, "
        "and Manager, the same chain of authority a paper sign-off would follow); and finalisation (the "
        "Officer closes out the file with the actual payment, representative detail, destruction record, or "
        "sale proceeds — the step that genuinely ends the file and locks in the audit trail). WMS-Trak's "
        "design follows this four-stage shape deliberately, so that the system mirrors how the work is "
        "already done rather than forcing officers to learn an unfamiliar process."
    )

    st.subheader("2.6 Chapter Summary")
    st.write(
        "This chapter has set out exactly what the Act requires — sixty days for RIH, ninety for an NOS "
        "appeal — named the specific weaknesses of the paper register that any officer on rotation would "
        "recognise, and explained why a purpose-built digital layer, rather than a change to ASYCUDA World "
        "itself, is the right response. Chapter Three sets out how this study went about building and "
        "testing that response."
    )

else:
    st.header("CHAPTER 3: RESEARCH METHODOLOGY")

    st.subheader("3.1 Research Design")
    st.write(
        "This study followed a design science research approach — the right fit for a piece of research "
        "that is judged, in the end, by whether the thing it built actually works. The cycle we followed was "
        "straightforward: confirm the legal and procedural ground first, build and refine the system in "
        "stages, put it in front of real officers, and evaluate it with a proper questionnaire and "
        "statistical test — feeding what we learned back into the system as we went, rather than treating "
        "design and evaluation as separate, one-off steps."
    )

    st.subheader("3.2 System Development Methodology")
    st.write(
        "The system was built module by module, in the order an officer would naturally encounter the "
        "work: login and role-based access first; then entry capture for RIH and NOS, including vehicle "
        "detail; then warehouse and vehicle-pound occupancy tracking; then the four-pathway disposal workflow "
        "with its Officer–Supervisor–Manager sign-off; then revenue capture and reporting at the point of "
        "finalisation; then the audit trail and internal messaging; and finally the pilot questionnaire and "
        "results module itself. Each module was built, tested against realistic scenarios drawn from actual "
        "desk experience, and deployed live before the next one was started — an incremental approach that "
        "let us catch a wrong assumption early rather than discover it after the whole system was built."
    )

    st.subheader("3.3 Population and Sampling")
    st.write(
        "The officers we needed to hear from were the ones who actually touch this process — Officers who "
        "capture and process RIH/NOS entries, Supervisors who give first-stage sign-off on disposal requests, "
        "and Managers who give final approval. We targeted roughly ten to fifteen officers at Forbes Border "
        "Post for pilot participation, a number that reflects realistically who was available to us within "
        "the training period at a single station."
    )

    st.subheader("3.4 Data Collection Instruments")
    st.write(
        "The main instrument was a 15-item questionnaire, answered directly inside the system by logged-in "
        "pilot users, using a 1 (Strongly Disagree) to 5 (Strongly Agree) scale. The fifteen items split into "
        "three groups of five, one for each research question — RQ1 on what the manual process actually got "
        "wrong, RQ2 on whether the digital system fixes it, and RQ3 on whether officers would actually want "
        "to use it. Each officer gets one response, which they can go back and edit — this avoided duplicate "
        "entries while still letting feedback evolve as officers grew more familiar with the system over the "
        "pilot period."
    )

    st.subheader("3.5 System Architecture and Development Tools")
    st.write(
        "WMS-Trak runs on Python 3.10/3.11 with Streamlit as the web framework, and PostgreSQL — hosted on "
        "Supabase, via its Session Pooler connection for reliable access from cloud environments — as the "
        "database, with psycopg2 handling database access through a connection pool for performance. The "
        "code lives in a private GitHub repository and deploys automatically to Streamlit Community Cloud on "
        "every update, so the pilot always runs the latest version without any manual reinstallation. "
        "Passwords are hashed with bcrypt, and login sessions persist across a page refresh through a "
        "server-side session-token table — so an officer mid-way through capturing a file does not lose their "
        "place if the page reloads."
    )

    st.subheader("3.6 Data Analysis Procedures")
    st.write(
        "Questionnaire responses were analysed with descriptive statistics (mean score per item and per "
        "research-question group), a reliability check (Cronbach's alpha) run separately for each five-item "
        "scale, and a paired-samples t-test comparing each officer's RQ1 score against their own RQ2 score — "
        "testing directly whether the digital system is seen as fixing the specific weaknesses officers named "
        "in the manual process. We set the bar for significance at p < 0.05, the conventional threshold. All "
        "of this analysis runs live inside the system itself (using SciPy), so it can be re-run at any time "
        "as more responses come in, rather than being a one-off calculation done outside the tool."
    )

    st.subheader("3.7 Ethical Considerations")
    st.write(
        "Participation was voluntary, limited to ZIMRA staff already using the system as part of their "
        "duties, and collected no personal detail beyond name, station, and role — used solely for this "
        "research and for improving the system itself. Access throughout was controlled by role-based login, "
        "on a database instance restricted to authorised access."
    )

    st.subheader("3.8 Chapter Summary")
    st.write(
        "This chapter has set out the design science approach we followed, how the system was built stage "
        "by stage, who we tested it with and how, the tools behind it, and how the pilot data is analysed. "
        "Chapter Four turns to the system itself — how it is put together and how it actually works on the "
        "floor."
    )