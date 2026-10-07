"""
User Manual — how to navigate and use Warehouse Management System, organised by role.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import streamlit as st

from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="User Manual — Warehouse Management System", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("User Manual — How to Use Warehouse Management System")

st.markdown("## Navigation")
st.write(
    "The left sidebar always shows the same things, no matter which "
    "role you're logged in as:"
)
st.markdown(
    "- **main** — your Dashboard\n"
    "- **Notifications** — system updates and chat-style messages\n"
    "- **About the Authors** — project information and the research group\n"
    "- **Research Paper** — the research behind the system\n"
    "- **User Manual** — this page\n"
    "- **Pilot Test Results** — results of the pilot questionnaire\n"
    "- **Account dropdown** (bottom of sidebar) — your profile, phone number, and Log out"
)
st.write(
    "Once logged in, you stay logged in even if you refresh the page or move "
    "between pages — you only get signed out by clicking **Log out**."
)

st.markdown("### The Dashboard buttons")
st.write(
    "At the top of your Dashboard is a row of **green buttons**, one for each "
    "screen available to your role. The bar stays fixed at the top while you "
    "scroll, so you can switch screens at any time."
)
st.markdown(
    "- The **selected** button is a deeper green with an **orange line** under it.\n"
    "- Hovering over a button shows an orange line under it.\n"
    "- If the buttons do not all fit on your screen, scroll the bar sideways: use "
    "the mouse wheel while pointing at it, click and drag it, swipe on a "
    "touchscreen, or use the grey scroll bar beneath it.\n"
    "- **Overview** is the first button. It shows entries whose bond/appeal "
    "deadline is approaching or overdue, perishable goods nearing physical expiry, "
    "and **Your Stocktake Rating**."
)

st.divider()

st.markdown("## Logging In")
st.write(
    "Enter your username (usually your ZIMRA email) and password on the "
    "sign-in screen. If your account is inactive or your details are wrong, "
    "you'll see an error — contact an Admin user to check your account status "
    "or reset your password."
)

st.divider()

st.markdown("## Printing and Downloading RIH and NOS Documents")
st.write(
    "Wherever the system shows a list of entries — My Captured Entries, Warehouses "
    "& Pounds, Request Action, Finalize Action, Released & Sold, the Overview "
    "tables, Warehouse Overview and the Admin screens — there is an option to "
    "**view the RIH (Receipt for Items Held) or NOS (Notice of Seizure)** for "
    "that entry."
)
st.markdown(
    "- The document is filled automatically from the entry's saved details and "
    "carries its **RIH No.** or **NOS No.** as recorded in the system, the ZIMRA logo, a "
    "round **WMS** stamp showing the date the entry was captured, and a **QR code** "
    "(top left) for verification.\n"
    "- Choose **Print** to send it to a printer, or **Download PDF** to save it.\n"
    "- If you correct an entry (Admin → Entry Correction), view the document "
    "again to get the updated version."
)

st.divider()

st.markdown("## Verifying a Document (QR Code)")
st.write(
    "Every RIH, NOS, closing document and auction notice printed from the system carries a "
    "QR code marked **Scan to verify**. Anyone — including the importer or a third party — "
    "can scan it with a phone camera. No login is needed."
)
st.markdown(
    "- The **Verify Document** page opens and shows **GENUINE**, with the document type and "
    "number, station, date, goods and current status. The name of the person the document was "
    "issued to is shown as initials only.\n"
    "- Compare those details with the paper. If anything differs, or the page says "
    "**NOT FOUND**, do not accept the document and report it to the nearest ZIMRA office.\n"
    "- If a QR code is damaged, open **Verify Document** from the sidebar and type the document "
    "type and number instead."
)

st.divider()

st.markdown("## Closing Documents")
st.write(
    "When an action has been **finalized**, the system can print the matching closing "
    "document. Open **Released & Sold**, and under the table use **Open closing document**: "
    "choose the entry, switch on the view, then **Print** or **Download PDF**."
)
st.markdown(
    "- **Release Receipt** — goods released to the owner: duty, additional duty, rent "
    "(days × daily rate), rent paid, total received, Y-number and clearance details, with "
    "signature lines for the person receiving the goods and the releasing Officer.\n"
    "- **Forfeiture / Appropriation Record** — the receiving Ministry, the request letter "
    "reference, the representative's name, ID and occupation, and what was handed over.\n"
    "- **Certificate of Destruction** — date and place, reason, Port Health Officer and "
    "approval reference, and who was present.\n"
    "- **E-Auction Sale Record** — revenue collected, buyer details, the auction receipt "
    "number and date of sale.\n"
    "- Each one also shows who requested, reviewed, approved and finalized the action, with "
    "dates, plus the WMS stamp and a verification QR code."
)

st.divider()

st.markdown("## E-Auctions and the Gazette Notice")
st.write(
    "Section 39(3) of the Customs and Excise Act requires **at least one month's notice in "
    "the Gazette** before RIH goods are sold by public auction. The system tracks this for you."
)
st.markdown(
    "1. In **Finalize Action**, an e-auction card now starts with a **Gazette notice** panel.\n"
    "2. Enter the **Gazette date**, the Gazette reference, the **auction date** and the platform. "
    "The system will not accept an auction date earlier than one calendar month after the "
    "Gazette date.\n"
    "3. Switch on **View / print Notice of E-Auction** to print or download the notice.\n"
    "4. The sale **cannot be finalized** until the notice period is complete — the panel shows "
    "how many days are left.\n"
    "5. Once it shows **Ready**, enter the revenue, buyer details and receipt number as usual.\n"
    "6. On your **Overview**, the **E-Auction Gazette Notice Tracking** table lists every "
    "e-auction awaiting finalization as *No Gazette notice*, *Waiting (days left)* or *Ready to sell*.\n"
    "- For **NOS** goods (forfeited to the State under section 193), the Gazette check does not apply."
)

st.divider()

st.markdown("## Transferring Goods or Vehicles Between Warehouses and Pounds")
st.write(
    "When goods must move from one warehouse to another, or a vehicle from one pound to "
    "another, the move is requested and approved in the system so the record always shows "
    "where the goods are. Transfers are within the same station."
)
st.markdown(
    "1. **Officer** — open **Transfers**, choose the entry, choose the destination "
    "warehouse or pound and give the reason, then submit.\n"
    "2. **Supervisor** — reviews the request under **Transfers** and approves or rejects it "
    "with notes.\n"
    "3. **Manager** — gives the final decision. The Supervisor must approve first.\n"
    "4. When the Manager approves, the goods are **moved automatically**: the entry's "
    "warehouse changes and the occupancy of both locations updates.\n"
    "5. Anyone involved can open the **movement history** of an entry and print or download "
    "the **Transfer Note** (with a verification QR code) to travel with the goods.\n"
    "- Only one transfer can be pending for an entry at a time.\n"
    "- If **Transfers** tells you your profile has no station, ask the Admin to assign your "
    "station under **Users**."
)

st.divider()

st.markdown("## Role-by-Role Guide")

with st.expander("👮 Officer", expanded=(user["role_name"] == "Officer")):
    st.markdown(
        "- **Overview**: deadlines, perishable-expiry warnings and your own "
        "stocktake rating.\n"
        "- **Capture Entry**: record a new RIH or NOS entry. Fill in importer/owner "
        "details, goods description, weight (with a kg/tonnes/litres/grams unit "
        "dropdown), rent charge per day, the ZWG-to-USD exchange rate, an expiry "
        "date if applicable, and (for NOS) seizure/legal details, or (for vehicles) "
        "vehicle specifics. Assign it to a Warehouse (A–E) or, if it's a vehicle, a "
        "Pound (A–E).\n"
        "- **My Captured Entries**: see everything you've personally captured, view "
        "full detail on any of them, and print or download its RIH/NOS.\n"
        "- **Warehouses & Pounds**: check occupancy at your station, mark a "
        "warehouse/pound Full or Not Full, and see what's currently stored in each.\n"
        "- **Request Action**: choose one of four pathways for an active entry:\n"
        "    - *Release to Owner* — goods released once duty/fines/rent are settled\n"
        "    - *Forfeiture* — appropriation to the State; specify the requesting "
        "Ministry and letter/document reference\n"
        "    - *Destruction* — for expired, dangerous, perishable, or prohibited "
        "goods; requires the approving Port Health officer and reason\n"
        "    - *E-Auction* — sale via ZIMRA's online auction system\n\n"
        "  Every request goes to your Supervisor for review.\n"
        "- **Finalize Action**: once Manager gives final approval, this is where "
        "the entry actually leaves active tracking. The form shown depends on the "
        "action type: Release to Owner asks for duty paid, additional duty, and "
        "rent paid (the system auto-calculates rent owed from your rent-per-day "
        "rate × days in the warehouse); Forfeiture asks for the receiving "
        "representative's details; Destruction asks for the date, place, and "
        "stakeholders present; E-Auction asks for revenue collected and buyer "
        "details. For an RIH e-auction, the Gazette notice must be recorded and the "
        "one-month period completed first. All require a receipt number where applicable.\n"
        "- **Transfers**: request a move of goods or a vehicle to another warehouse "
        "or pound, and follow its approval.\n"
        "- **Released & Sold**: see everything that's left active tracking at your "
        "station, plus running revenue totals, and print the closing document for "
        "any finalized entry.\n"
        "- **Stocktake Reports**: results of the latest stocktakes at your station "
        "and the monthly report (see *Stocktake and Ratings* below). You do not "
        "count stock yourself."
    )

with st.expander("🧭 Supervisor", expanded=(user["role_name"] == "Supervisor")):
    st.markdown(
        "- **Overview**: deadlines, perishable-expiry warnings and your own "
        "stocktake rating.\n"
        "- **Review Requests**: Officer-submitted requests at your station land "
        "here first, regardless of action type. Approve to forward to the "
        "Manager, or reject with a reason.\n"
        "- **Transfers**: approve or reject Officer requests to move goods or vehicles "
        "between warehouses/pounds at your station; Manager decides next.\n"
        "- **Warehouse Overview**: RIH list, Seizures list, and a monthly summary "
        "for your station — filterable by warehouse and date range.\n"
        "- **Released & Sold**: everything finalized at your station, with revenue "
        "totals.\n"
        "- **Stocktake Reports**: stocktake results and monthly reports for your "
        "station, with the ratings of the officers at your station and your own "
        "rating for the goods you approved."
    )

with st.expander("✅ Manager", expanded=(user["role_name"] == "Manager")):
    st.markdown(
        "- **Overview**: deadlines, perishable-expiry warnings and your own "
        "stocktake rating.\n"
        "- **Final Approvals**: requests already approved by a Supervisor land "
        "here, from all ports. Approving here grants **permission** — the entry "
        "moves to 'awaiting finalization,' but stays in active tracking until the "
        "Officer completes the finalization step.\n"
        "- **Transfers**: give the final decision on transfers a Supervisor has approved. "
        "Approving moves the goods automatically.\n"
        "- **Warehouse Overview**: same as Supervisor's, but across all ports.\n"
        "- **Released & Sold**: system-wide revenue totals and finalized entries.\n"
        "- **Stocktake Reports**: results and monthly reports for all stations, "
        "with the ratings of every supervisor and officer, and your own rating for "
        "the goods you approved."
    )

with st.expander("🛠️ Admin", expanded=(user["role_name"] == "Admin")):
    st.markdown(
        "- **Overview**: deadlines and perishable-expiry warnings.\n"
        "- **Profile Requests**: review requests for new profiles.\n"
        "- **Users**: create new accounts (Officer, Supervisor, Manager, Admin), "
        "deactivate/reactivate accounts, reset passwords, or delete a user.\n"
        "- **Entry Correction**: search for an entry and fix mistakes (entry number, "
        "description, declared value) — every correction is logged with a reason.\n"
        "- **Audit Trail**: full history of every action taken in the system, plus a "
        "live list of currently detained goods with the officer responsible.\n"
        "- **Messages**: moderate the Messages feed — delete anything inappropriate "
        "or posted in error.\n"
        "- **Statistics**: total revenue collected, warehouse usage across all "
        "stations, and RIH entries sorted by days remaining until expiry.\n"
        "- **Warehouse Overview**: same filterable view available to Manager.\n"
        "- **Transfers**: view all transfer requests and the movement history of goods "
        "across warehouses and pounds.\n"
        "- **Stocktake**: the audit count. Only the Admin counts stock (see below).\n"
        "- **Stocktake Reports**: results and ratings for everyone."
    )

st.divider()

st.markdown("## Stocktake and Ratings")
st.write(
    "A stocktake is an **audit**: the physical goods in a warehouse are checked "
    "against what the system says should be there. Because Officers, Supervisors "
    "and Managers are the people being audited, **only the Admin carries out "
    "stocktakes**, and may do so at any time. A stocktake is expected for every "
    "warehouse **once a month**."
)

st.markdown("### How the Admin counts")
st.markdown(
    "1. Open **Stocktake**. The **progress table** at the top lists every "
    "warehouse for the current month as **Completed** (with the date and score), "
    "**In progress**, or **Due for Stocktake**.\n"
    "2. Pick a warehouse and press **Start a new stocktake**. The system lists "
    "every entry it expects to find there.\n"
    "3. Tick each item that is physically present. Anything left unticked is "
    "recorded as **missing**.\n"
    "4. Record any goods found that are **not on the system list** as extra items.\n"
    "5. Press **Close stocktake and score it**. The score and a PDF report are produced."
)

st.markdown("### How it is scored")
st.write(
    "Each stocktake is marked **out of 100**: items present divided by "
    "(items expected + extra items found), times 100."
)
st.markdown(
    "- **95 or above — Pass.** 100 is the target and a variance of up to 5% is accepted.\n"
    "- **Below 95 — Flagged for potential fraud.** Every missing entry is flagged "
    "together with the **responsible officer**, and the supervisor and manager "
    "who approved it. They are notified in **Notifications**."
)

st.markdown("### What everyone else sees")
st.markdown(
    "- **Stocktake Reports** tab: recent stocktake results with downloadable "
    "reports, and a **monthly report**. Completed months are available after "
    "month-end; the current month can be requested at any time as *month to date*.\n"
    "- Each report shows the score, revenue collected, goods in stock, and RIH and "
    "NOS broken down by category (for example Vehicles, Drinks, Clothing, "
    "Perishables, depending on what is in the warehouse), plus flagged entries and "
    "the officers responsible.\n"
    "- **Your Stocktake Rating** on the Overview shows only your own score. If you "
    "did not enter goods into the warehouse, it says so instead of showing a score — "
    "you can still open the station's reports.\n"
    "- **Who sees whose rating:** an Officer sees their own; a Supervisor sees the "
    "officers at their station and their own rating for goods they approved; a "
    "Manager sees all supervisors and officers; the Admin sees everyone."
)

st.divider()

st.markdown("## Notifications")
st.write(
    "Open **Notifications** from the sidebar. It has two tabs:"
)
st.markdown(
    "- **System Notifications**: automatic updates — entries awaiting your action, "
    "approvals, rejections, stocktake flags. Mark them read as you go.\n"
    "- **Messages**: a chat-style feed for human communication — send a message to "
    "everyone (ZIMRA-wide announcement), to a specific role, or to one person."
)

st.divider()

st.markdown("## The Release / Disposal Workflow, End to End")
st.markdown(
    "1. **Officer** captures the RIH/NOS entry.\n"
    "2. **Officer** requests one of four actions: **Release to Owner**, "
    "**Forfeiture**, **Destruction**, or **E-Auction** — with any type-specific "
    "details required at request time (e.g. Ministry name for Forfeiture, Port "
    "Health approval for Destruction).\n"
    "3. **Supervisor** reviews the request — approve to forward, or reject.\n"
    "4. **Manager** gives final approval — this grants **permission**, but does "
    "not yet remove the entry from active tracking.\n"
    "5. **Officer** finalizes the action — records the type-specific closing "
    "details (payment breakdown and auto-calculated rent for Release to Owner; "
    "representative details for Forfeiture; destruction date/place/stakeholders "
    "for Destruction; revenue and buyer details for E-Auction). **This step is "
    "what actually effects the action** and removes the entry from active stock.\n"
    "6. The entry now appears in everyone's **Released & Sold** tab within their "
    "jurisdiction, contributing to revenue totals."
)