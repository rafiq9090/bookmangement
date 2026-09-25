import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_report():
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Color Palette
    PRIMARY = RGBColor(30, 41, 59)      # Slate Navy #1E293B
    ACCENT = RGBColor(255, 90, 31)      # Vibrant Orange #FF5A1F
    SECONDARY = RGBColor(15, 118, 110)  # Emerald Teal #0F766E
    MUTED = RGBColor(100, 116, 139)     # Cool Gray #64748B
    DARK_TEXT = RGBColor(15, 23, 42)    # Slate 900 #0F172A

    # Helper function to style cells
    def set_cell_background(cell, hex_color):
        shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading_elm)

    def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for margin_name, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
            node = OxmlElement(margin_name)
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    def add_custom_heading(text, level, color=PRIMARY, space_before=14, space_after=6):
        h = doc.add_heading(level=level)
        h.paragraph_format.space_before = Pt(space_before)
        h.paragraph_format.space_after = Pt(space_after)
        run = h.add_run(text)
        run.font.name = 'Calibri'
        run.font.bold = True
        run.font.color.rgb = color
        if level == 1:
            run.font.size = Pt(18)
        elif level == 2:
            run.font.size = Pt(14)
        elif level == 3:
            run.font.size = Pt(12)
        return h

    def add_p(text="", bold=False, italic=False, color=DARK_TEXT, size=11, space_after=6, align=WD_ALIGN_PARAGRAPH.LEFT):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if text:
            run = p.add_run(text)
            run.font.name = 'Calibri'
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = color
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Calibri'
        r_pre.font.size = Pt(11)
        r_pre.font.bold = True
        r_pre.font.color.rgb = PRIMARY
        
        r_text = p.add_run(text)
        r_text.font.name = 'Calibri'
        r_text.font.size = Pt(11)
        r_text.font.color.rgb = DARK_TEXT

    # ------------------ COVER / HEADER TITLE ------------------
    cover_top_space = doc.add_paragraph()
    cover_top_space.paragraph_format.space_before = Pt(24)

    p_badge = doc.add_paragraph()
    p_badge.paragraph_format.space_after = Pt(8)
    r_badge = p_badge.add_run("SOFTWARE ENGINEERING PROJECT REPORT")
    r_badge.font.name = 'Calibri'
    r_badge.font.size = Pt(10)
    r_badge.font.bold = True
    r_badge.font.color.rgb = ACCENT

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("Old & Rare Book Multi-Vendor Marketplace")
    r_title.font.name = 'Calibri'
    r_title.font.size = Pt(26)
    r_title.font.bold = True
    r_title.font.color.rgb = PRIMARY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(24)
    r_sub = p_sub.add_run("A Scalable, Secure E-Commerce & In-App Inquiry Platform for Vintage, Out-of-Print, and Used Books")
    r_sub.font.name = 'Calibri'
    r_sub.font.size = Pt(13)
    r_sub.font.italic = True
    r_sub.font.color.rgb = MUTED

    # Meta Table (Team & Project Overview)
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Project Title:", "Old & Rare Book Management & Marketplace System"),
        ("Project Lead & Author:", "Md. Rafiqul Islam (Lead Developer & System Architect)"),
        ("Team Member 2:", "[Team Member 2 Name] (Frontend & UI/UX Developer)"),
        ("Team Member 3:", "[Team Member 3 Name] (Database & Quality Assurance Engineer)"),
        ("Technology Stack:", "Django 5.1, PostgreSQL 16, Redis 7, Celery, Tailwind CSS, Docker")
    ]
    for i, (k, v) in enumerate(meta_data):
        row = meta_table.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        set_cell_background(c0, "F1F5F9")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 80, 80, 100, 100)
        set_cell_margins(c1, 80, 80, 100, 100)
        
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        r0.font.name = 'Calibri'
        r0.font.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = PRIMARY
        
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        r1.font.name = 'Calibri'
        r1.font.size = Pt(10)
        r1.font.color.rgb = DARK_TEXT

    doc.add_page_break()

    # ------------------ EXECUTIVE SUMMARY ------------------
    add_custom_heading("Executive Summary", level=1, color=PRIMARY)
    add_p(
        "The Old & Rare Book Marketplace is a full-featured, enterprise-grade multi-vendor platform engineered specifically to address the unique complexities of buying, selling, and authenticating second-hand, antique, out-of-print, and collectible books. Unlike commoditized e-commerce systems that assume homogeneous stock, this platform manages individual book condition gradings, high-resolution physical inspection imagery, buyer-seller pre-purchase negotiation/condition verification, split multi-vendor logistics, and an automated financial escrow mechanism."
    )
    add_p(
        "Developed using Python 3.12, Django 5.1, PostgreSQL, Redis, and Celery, the platform guarantees atomic concurrency protection against double-purchasing of one-of-a-kind vintage copies, provides responsive buyer-seller communication with real-time condition inquiries, and implements strict multi-vendor ledger accounting."
    )

    # ------------------ 1. EXPECTATIONS & OBJECTIVES ------------------
    add_custom_heading("1. Project Expectations & Scope", level=1, color=PRIMARY)
    add_p(
        "Standard e-commerce marketplaces fail vintage and used book collectors because each pre-owned book has a unique physical state (wear, binding strength, missing pages, annotations, discoloration, and rarity). The project was initiated with clear core expectations:"
    )
    add_bullet("Accurate Physical Condition Transparency: ", "Allow sellers to classify copies using industry-standard condition grades (As New, Fine, Very Good, Good, Fair, Poor) backed by multiple high-resolution photos.")
    add_bullet("Buyer Trust & Verification Workflow: ", "Require or encourage direct pre-order condition inquiries where buyers can request additional photos or negotiate before checkout is unlocked.")
    add_bullet("Zero Double-Selling of Unique Inventory: ", "Guarantee that rare, single-copy book listings cannot be concurrently purchased by multiple customers simultaneously via Redis-backed reservation locking.")
    add_bullet("Multi-Vendor Order & Shipment Splitting: ", "Enable buyers to purchase from multiple distinct sellers in a single checkout while automatically splitting shipments, tracking codes, and delivery statuses per vendor.")
    add_bullet("Financial Protection & Escrow Holds: ", "Secure buyer payments in escrow until delivery is verified, ensuring fraud protection before crediting seller ledgers.")

    # ------------------ 2. SYSTEM ARCHITECTURE & TECH STACK ------------------
    add_custom_heading("2. System Architecture & Technology Stack", level=1, color=PRIMARY)
    add_p(
        "The system follows a clean modular monolith architecture with containerized services for maximum maintainability and horizontal scalability."
    )

    tech_table = doc.add_table(rows=7, cols=3)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Layer / Component", "Technology Selected", "Functional Purpose"]
    for j, h_text in enumerate(headers):
        cell = tech_table.rows[0].cells[j]
        set_cell_background(cell, "1E293B")
        set_cell_margins(cell, 100, 100, 120, 120)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.name = 'Calibri'
        r.font.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    tech_rows = [
        ("Backend Framework", "Django 5.1 & Django REST Framework", "Modular MVC architecture, ORM, authentication, and RESTful API endpoints"),
        ("Database Engine", "PostgreSQL 16", "ACID transactions, relational constraints, and JSONB for address/event snapshots"),
        ("Caching & Locks", "Redis 7", "15-minute TTL reservation locks for listings during checkout, session caching"),
        ("Asynchronous Tasks", "Celery + Redis Broker", "Automated WebP image compression, expired lock cleanup, email triggers"),
        ("Frontend & Styling", "Tailwind CSS + Vanilla JS + HTML5", "Modern responsive UI, custom design system, tabbed navigation, modals"),
        ("Containerization", "Docker & Docker Compose", "Orchestrates web application, PostgreSQL database, and Redis cache")
    ]
    for i, row_data in enumerate(tech_rows, start=1):
        row = tech_table.rows[i]
        bg_col = "F8FAFC" if i % 2 == 1 else "FFFFFF"
        for j, text in enumerate(row_data):
            c = row.cells[j]
            set_cell_background(c, bg_col)
            set_cell_margins(c, 80, 80, 100, 100)
            p = c.paragraphs[0]
            r = p.add_run(text)
            r.font.name = 'Calibri'
            r.font.size = Pt(9.5)
            if j == 0:
                r.font.bold = True
                r.font.color.rgb = PRIMARY
            else:
                r.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_before = Pt(8)

    # ------------------ 3. CORE MODULES ------------------
    add_custom_heading("3. Core Modules Breakdown", level=1, color=PRIMARY)
    add_p(
        "The project is structured under the 'apps/' root with clean domain boundaries, eliminating circular dependencies:"
    )

    modules_data = [
        ("3.1 Accounts Module (apps.accounts)", [
            ("CustomUser Model: ", "Custom authentication supporting email-first login, roles (Buyer, Seller, Administrator), and profile management."),
            ("SellerProfile Model: ", "Store name, biography, NID/KYC verification status, payout configuration (bKash, Nagad, Bank transfer), and aggregate star ratings."),
            ("Address Management: ", "Multi-address delivery book with default address toggling, city, state/division, postal codes, and recipient contact info.")
        ]),
        ("3.2 Books Catalog Module (apps.books)", [
            ("Canonical Book Registry: ", "ISBN-10, ISBN-13, master title, publication year, publisher, language, and cover image."),
            ("Authors & Taxonomies: ", "Relational models for book authors with biographies, photos, and hierarchical parent-child category trees."),
            ("Community Reviews: ", "Star rating system (1-5 stars) with headline and text feedback, including anti-self-review safeguards for sellers.")
        ]),
        ("3.3 Listings Module (apps.listings)", [
            ("BookListing Inventory: ", "Multi-vendor inventory connecting sellers to master book records with price, original MRP, edition year, and hardcover flag."),
            ("Condition Grading System: ", "Predefined wear scale (As New, Fine, Very Good, Good, Fair, Poor) with mandatory seller notes."),
            ("Inspection Imagery: ", "Multiple real-copy photo uploads per listing, processed into optimized WebP formats.")
        ]),
        ("3.4 Orders & Fulfillment Module (apps.orders)", [
            ("Cart & Session Management: ", "Dynamic multi-item cart system supporting listings from multiple independent sellers."),
            ("Multi-Vendor Order Splitting: ", "Master Order record automatically splits into individual 'OrderShipment' instances per seller."),
            ("Concurrency Protection: ", "Atomic reservation locks prevent simultaneous checkout of unique pre-owned listings.")
        ]),
        ("3.5 Messaging & Inquiries Module (apps.messaging)", [
            ("Conversation Threads: ", "Direct messaging between prospective buyer and seller tied to a specific listing copy."),
            ("Photo & Condition Inquiries: ", "Buyers can request close-up photo evidence of book spines, pages, or bindings prior to purchase."),
            ("Purchase Authorization: ", "Sellers can approve availability and confirm agreed pricing directly from chat, unlocking checkout.")
        ]),
        ("3.6 Payments & Escrow Module (apps.payments)", [
            ("Payment Gateway Integration: ", "Supports automated and manual payment verification (bKash, Nagad, Cards, Cash-on-Delivery)."),
            ("Escrow Hold Mechanism: ", "Buyer funds are held in escrow and released to the seller ledger only upon confirmed delivery."),
            ("Seller Financial Ledger: ", "Transparent accounting for gross sales, platform commission deductions, and net payout batches.")
        ]),
        ("3.7 Shipping & Logistics Module (apps.shipping)", [
            ("Courier Integration: ", "Pluggable provider models for courier dispatch (Pathao, Steadfast, RedX)."),
            ("Tracking Events: ", "Timestamped chronological tracking logs updated via courier webhooks.")
        ])
    ]

    for mod_title, mod_items in modules_data:
        add_custom_heading(mod_title, level=2, color=SECONDARY, space_before=10, space_after=4)
        for prefix, desc in mod_items:
            add_bullet(prefix, desc)

    # ------------------ 4. OUTCOMES & ACCOMPLISHMENTS ------------------
    add_custom_heading("4. Project Outcomes & Accomplishments", level=1, color=PRIMARY)
    add_p(
        "The project has achieved significant technical and functional milestones, resulting in a production-ready web application:"
    )
    add_bullet("Fully Operational Multi-Vendor Platform: ", "Seamless workflow from seller onboarding and book cataloging to listing creation, cart handling, and multi-vendor checkout.")
    add_bullet("Elimination of Catalog Redundancy: ", "Canonical book entries decouple universal bibliographic data from individual seller copies, keeping search clean while supporting multiple competing offers.")
    add_bullet("Interactive Buyer-Seller Chat & Order Unlock: ", "Implemented the specialized inquiry loop where buyers verify physical condition before payment is activated.")
    add_bullet("Refined Modern User Interface: ", "Tailwind CSS design featuring responsive hero showcases, tabbed specifications, interactive photo switchers, and quick contact action buttons.")
    add_bullet("High Code Quality & Schema Validation: ", "Passes Django system checks with zero warnings, OpenAPI 3.0 specification compliance, and modular configuration splits.")

    # ------------------ 5. DISTRIBUTION OF WORK ------------------
    add_custom_heading("5. Distribution of Work", level=1, color=PRIMARY)
    add_p(
        "The work was strategically distributed across three team members to cover architecture, backend engineering, user interface, database optimization, and quality assurance:"
    )

    work_table = doc.add_table(rows=4, cols=3)
    work_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    w_headers = ["Team Member", "Assigned Role", "Key Responsibilities & Deliverables"]
    for j, h_text in enumerate(w_headers):
        cell = work_table.rows[0].cells[j]
        set_cell_background(cell, "1E293B")
        set_cell_margins(cell, 100, 100, 120, 120)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.name = 'Calibri'
        r.font.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    team_assignments = [
        ("Md. Rafiqul Islam\n(Project Lead)", "System Architect & Lead Backend Developer", 
         "• Overall project design, environment setup, and Django modular architecture.\n"
         "• Implementation of Books, Listings, Orders, and Messaging apps.\n"
         "• Concurrency control with Redis 15-minute lock reservation.\n"
         "• Multi-vendor shipment splitting and Escrow payment logic.\n"
         "• API endpoint development and system integration."),
        ("[Team Member 2 Name]", "Frontend & UI/UX Developer", 
         "• Responsive template design with Tailwind CSS and FontAwesome.\n"
         "• Interactive Book Detail Showcase (tabs, image switchers, review forms).\n"
         "• Cart, Checkout, and Seller Dashboard responsive user interfaces.\n"
         "• Client-side validation, clipboard helpers, and dynamic modals.\n"
         "• Cross-browser testing and mobile layout optimization."),
        ("[Team Member 3 Name]", "Database, QA & DevOps Engineer", 
         "• Database schema design, indexing, and migration management in PostgreSQL.\n"
         "• Docker Compose setup for web, PostgreSQL, and Redis containers.\n"
         "• Comprehensive manual and unit testing of APIs and checkout flows.\n"
         "• Test dataset seeding (fixtures for books, authors, and sample listings).\n"
         "• System documentation, OpenAPI/Swagger validation, and technical reports.")
    ]

    for i, row_data in enumerate(team_assignments, start=1):
        row = work_table.rows[i]
        bg_col = "F8FAFC" if i % 2 == 1 else "FFFFFF"
        for j, text in enumerate(row_data):
            c = row.cells[j]
            set_cell_background(c, bg_col)
            set_cell_margins(c, 80, 80, 100, 100)
            p = c.paragraphs[0]
            r = p.add_run(text)
            r.font.name = 'Calibri'
            r.font.size = Pt(9.5)
            if j == 0:
                r.font.bold = True
                r.font.color.rgb = PRIMARY
            else:
                r.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_before = Pt(8)

    # ------------------ 6. FUTURE WORK & ROADMAP ------------------
    add_custom_heading("6. Future Work & Enhancements", level=1, color=PRIMARY)
    add_p(
        "To scale the platform into a leading commercial marketplace for rare books, several advanced features are planned for upcoming releases:"
    )
    add_bullet("AI-Powered Book Wear Assessment: ", "Computer vision integration to inspect book cover and spine uploads, automatically suggesting condition grades and flagging torn pages or water damage.")
    add_bullet("Mobile Application (Flutter / React Native): ", "Native mobile app for sellers to quickly scan ISBN barcodes with their smartphone camera and auto-populate bibliographic book details.")
    add_bullet("Automated Courier Dispatch Webhooks: ", "Direct API integration with national courier services (Pathao, Steadfast) for instant parcel pickup generation and automated shipping label printing.")
    add_bullet("Live WebSocket Chat: ", "Upgrade buyer-seller condition inquiries to instant WebSockets via Django Channels for real-time messaging and typing indicators.")
    add_bullet("Rare Book Auction Engine: ", "Add an auction bidding module for high-value antique first editions and autographed historical manuscripts.")

    # ------------------ 7. CONCLUSION ------------------
    add_custom_heading("7. Conclusion", level=1, color=PRIMARY)
    add_p(
        "The Old & Rare Book Multi-Vendor Marketplace successfully bridges the gap between conventional e-commerce platforms and the niche requirements of collectible and second-hand book trading. By combining robust Django architecture, atomic inventory reservations, multi-vendor order splitting, transparent condition reporting, and secure escrow mechanisms, the platform delivers an authentic, secure, and delightful experience for book lovers, collectors, and independent booksellers alike."
    )

    output_path = os.path.abspath("Old_and_Rare_Book_Marketplace_Project_Report.docx")
    doc.save(output_path)
    print(f"Report generated successfully at: {output_path}")

if __name__ == "__main__":
    create_report()
