# 實作待確認問題清單

> 實作過程中發現任何無法自行判斷的問題即寫入此文件，不靠記憶。解決後在問題後標記 [已解決]。

---

## OUTPUT 2: QUESTIONS LIST

### A. GENERAL ARCHITECTURE

1. **Database Type Confirmation**
   - Module affected: All
   - Question: Is PostgreSQL with async SQLAlchemy + asyncpg the final choice? Any alternative DB considerations?
   - Why it matters: ORM setup, migration strategy, concurrency model depend on this decision

2. **Deployment & Environment**
   - Module affected: All
   - Question: Confirmed Railway for both prod and dev? Any staging environment needed?
   - Why it matters: Affects environment variable setup, database strategy, webhook URL configuration

3. **Frontend Technology Stack**
   - Module affected: All
   - Question: What is the frontend framework (React/Vue/Svelte)? Do we need CORS configuration guidance?
   - Why it matters: Cookie settings (httpOnly, SameSite), CORS allowed origins affect backend response headers

4. **CI/CD Pipeline**
   - Module affected: All
   - Question: How are migrations auto-applied on deployment? Manual approval required?
   - Why it matters: Risk of schema mismatches between code and database

---

### B. AUTH & USER MANAGEMENT

5. **Admin Account Creation**
   - Modules affected: Auth, User Management
   - Question: Should the `create_admin.py` script also set up a default admin email/password template, or is this completely manual?
   - Why it matters: Affects onboarding safety (weak default passwords?)

6. **OAuth / Social Login**
   - Modules affected: Auth, User Profile
   - Question: Should Google/Facebook login be implemented alongside email/password? Or is email-only acceptable for MVP?
   - Why it matters: Affects user registration flow, OAuth provider configuration

7. **Admin Auto-Logout Duration**
   - Modules affected: Auth
   - Question: Admin JWT expires in 8 hours. Should there be automatic redirect to login, or just silent 401 in API? How should front-end handle this?
   - Why it matters: UX for long-running sessions, cache management

8. **Email Domain for Verification**
   - Modules affected: Auth
   - Question: What domain/sender name for verification emails (e.g., noreply@paintlearn.com)? Should this be configurable in system_settings?
   - Why it matters: Email deliverability, branding

9. **Password Reset Token Cleanup**
   - Modules affected: Auth
   - Question: Should expired password_reset_tokens be auto-deleted from the DB, or retained for audit?
   - Why it matters: Database bloat vs. compliance/audit trail

---

### C. PRODUCTS & VARIANTS

10. **Variant Uniqueness & Replacement**
    - Modules affected: Products Management, Production System
    - Question: UNIQUE(product_id, production_job_id) with ON CONFLICT UPDATE is mentioned. Should this also clear old palette_color_mappings records?
    - Why it matters: Affects color remapping workflow when reusing production_jobs

11. **Product Series Cascading**
    - Modules affected: Products Management, Products Browsing
    - Question: When deleting a series, should associated products be auto-unset or should deletion be blocked? Current spec says blocked.
    - Why it matters: User experience for admin (error vs. cleanup)

12. **Product Images Soft-Delete**
    - Modules affected: Products Management
    - Question: Are deleted product_images permanently removed from Firebase, or kept for historical reference?
    - Why it matters: Storage cost, recovery options if deletion was accidental

13. **Tag Bulk Operations**
    - Modules affected: Products Management
    - Question: Should there be a bulk endpoint to assign/remove tags from multiple products, or is single-product tagging sufficient?
    - Why it matters: Admin efficiency, API design

---

### D. PRODUCTION SYSTEM

14. **SAM Model Memory & Concurrency**
    - Modules affected: Production System
    - Question: SAM model is single-instance in-memory. What happens if two concurrent users request SAM processing? Queue them, or reject with "model busy"?
    - Why it matters: Affects Celery queue management, user experience for heavy concurrent load

15. **Production Job Batch Failure Handling**
    - Modules affected: Production System
    - Question: If one job in a batch fails, should subsequent jobs be auto-cancelled or require admin retry? Current spec says auto-cancelled.
    - Why it matters: Loss of work, admin communication needed

16. **Post-Processing & Approved Status**
    - Modules affected: Production System, Color Management
    - Question: Each post-process (merge, eliminate, smooth) sets approved=false. Should admin be notified, or is silent reset acceptable?
    - Why it matters: Prevents accidental missed re-approval

17. **PDF Export Caching**
    - Modules affected: Production System
    - Question: Each PDF export regenerates from SVG (Inkscape call). Should results be cached? TTL if cached?
    - Why it matters: Performance, consistency (SVG changes should trigger re-export)

18. **Temporary File Cleanup**
    - Modules affected: Production System
    - Question: When Celery downloads custom_request photos to temp storage, how long before cleanup if job fails? Immediate or time-based?
    - Why it matters: Disk space management, recovery options

19. **Production Job Status Polling**
    - Modules affected: Production System
    - Question: Should admin UI poll /admin/production/jobs/{id} for status updates, or use SSE/WebSocket like notifications?
    - Why it matters: Server load, real-time feedback quality

---

### E. COLOR MANAGEMENT & INVENTORY

20. **Stock Reserved vs. Committed**
    - Modules affected: Color Management, Orders
    - Question: Current spec deducts stock_ml at order creation (pending_payment). What if payment fails after 24h? Stock is already "reserved" but order cancelled. Is this acceptable?
    - Why it matters: Inventory accuracy perception (double-count risk if not handled)

21. **LAB Color Distance Library**
    - Modules affected: Color Management
    - Question: Which library for RGB ↔ LAB conversion? (e.g., scikit-image, PIL, custom implementation?)
    - Why it matters: Accuracy of auto-mapping, performance

22. **Color Code Uniqueness**
    - Modules affected: Color Management
    - Question: physical_colors.code (e.g., "201") — is this globally unique across all suppliers, or can different suppliers have code "201"?
    - Why it matters: Affects color deduplication, brand tracking

23. **Stock Update Notification Spam**
    - Modules affected: Color Management
    - Question: Every admin stock update triggers preorder fulfillment scan. Should there be a batch update endpoint to avoid multiple scans?
    - Why it matters: Performance, email notification spam to customers

24. **Palette Mapping Copy Scope**
    - Modules affected: Color Management
    - Question: "Copy from other job" — should it copy ONLY completed mapping colors, or include partial mappings?
    - Why it matters: Data integrity, admin usability

---

### F. ORDERS & CHECKOUT

25. **Preorder Quantity Logic**
    - Modules affected: Orders, Color Management
    - Question: If customer orders 5 units but only 2 in stock, order_items.fulfilled_qty=2, preorder_qty=3. When fulfilling preorder later, is it per-color or per-order-item?
    - Why it matters: Complex multi-color scenarios (e.g., some colors replenish before others)

26. **Shipping Fee on Partial Refund**
    - Modules affected: Orders
    - Question: If customer gets partial refund but shipped once (one shipping fee charged), how is fee apportioned in refund? Full credit or pro-rata?
    - Why it matters: Customer fairness, refund logic clarity

27. **Separate Shipments & Duplicate Fees**
    - Modules affected: Orders
    - Question: "Select separate shipment" → two shipping fees charged, but "not collected twice from customer." Where is cost absorbed? Margin reduction?
    - Why it matters: Business model clarity, cost accounting

28. **Order Number Collision Protection**
    - Modules affected: Orders
    - Question: PostgreSQL SEQUENCE is used for order_number. Is there failover/replication risk? How is this tested for consistency?
    - Why it matters: Order number uniqueness guarantee under failure

29. **Payment Verification Workflow**
    - Modules affected: Orders
    - Question: Manual bank transfer verification — is there a target SLA for "payment confirmed" after customer submits transfer info? Auto-confirm? Manual?
    - Why it matters: Customer experience (when can they see "paid" status?)

30. **Order Cancellation by Admin** [已解決]
    - Modules affected: Orders
    - Answer: Admin can only directly cancel `pending_payment` orders. For `paid` and beyond, must use refund flow (`refund_processing` → `refunded` / `partially_refunded`). Direct cancel to `cancelled` status is blocked at API level for paid orders.

31. **Multiple Payment Submissions**
    - Modules affected: Orders
    - Question: Customer can re-submit payment info multiple times. Should old submissions be soft-deleted, hidden, or all kept visible?
    - Why it matters: Audit trail, UI clutter

32. **Coupon Reversion on Refund**
    - Modules affected: Orders, Coupons
    - Question: If order with coupon is refunded, coupon reverts to is_used=false. Can customer use it again immediately, or wait for new order?
    - Why it matters: Coupon cycle clarity

33. **Double-Sided Shipping Validation**
    - Modules affected: Orders, Shipping Profiles
    - Question: Shipping address validation (city, district, address_detail for home shipping) — who validates? Front-end, backend, or third-party?
    - Why it matters: Data quality, error handling

---

### G. CUSTOM REQUESTS

34. **Photo Upload Size Limits**
    - Modules affected: Custom Requests
    - Question: 10MB limit mentioned in spec. Should this be enforced front-end only, or also backend (reject oversized Firebase URLs)?
    - Why it matters: Security, user feedback clarity

35. **Custom Photo Private Access**
    - Modules affected: Custom Requests, Production System
    - Question: Signed URLs for private photos (15min TTL). What happens if admin's session expires mid-quotation? Re-request URL, or extend?
    - Why it matters: UX for admin during long quotation sessions

36. **Quote Token Security**
    - Modules affected: Custom Requests
    - Question: Quote token is hashed in DB. Is it emailed as plaintext or hashed? If plaintext, how is collision risk managed?
    - Why it matters: Security best practices, token leakage scenarios

37. **Reapply Custom Request**
    - Modules affected: Custom Requests
    - Question: Customer rejects quote & reapplies. Should new request auto-inherit previous parameters, or require re-entry?
    - Why it matters: User experience, data consistency

38. **Message Only, No File Attachments**
    - Modules affected: Custom Requests
    - Question: Pure text messages only. What if customer wants to update/replace photo? Via "update photo" button only, not inline message?
    - Why it matters: UX clarity, file organization

39. **SSE Connection Stability**
    - Modules affected: Custom Requests, Notifications
    - Question: SSE connections can drop on proxies/firewalls. Is exponential backoff + reconnect the plan?
    - Why it matters: Reliability, debugging dropped messages

40. **Message Read Status**
    - Modules affected: Custom Requests
    - Question: Messages don't have "read" status. Should there be optional "typing indicator" or real-time message delivery feedback?
    - Why it matters: Communication clarity, user expectations

---

### H. DISCOUNTS & PRICING

41. **Auto-Checkout Overlap**
    - Modules affected: Discounts
    - Question: Multiple auto_checkout configs active simultaneously (e.g., one expires tomorrow, one expires next week). Should all be visible to admin, or only active ones?
    - Why it matters: Discount management complexity

42. **Coupon Expiration Calculation**
    - Modules affected: Discounts
    - Question: valid_days parameter (e.g., 30). Is expiry = issued_at + 30 days at same time, or next midnight?
    - Why it matters: Boundary cases (issued at 23:59, should it expire in 24h or next day at midnight?)

43. **Coupon Minimum Purchase Enforcement**
    - Modules affected: Discounts, Orders
    - Question: Coupon has min_purchase (e.g., NT$500). If discount applied, is threshold calculated on original subtotal (before discount) or final?
    - Why it matters: Coupon stacking prevention clarity

44. **Returning Loyal Trigger Threshold**
    - Modules affected: Discounts, Orders
    - Question: returning_loyal requires prior completed orders. What if user has 1 order completed at NT$999? Next order at NT$1000 triggers coupon?
    - Why it matters: Customer fairness, edge cases

45. **Manual Coupon Expiry**
    - Modules affected: Discounts
    - Question: Manual coupons assigned by admin don't reference coupon_configs. How is expiry_date specified in UI? Hard-coded "one year from now" or admin-set?
    - Why it matters: Admin control, data model clarity

46. **Promo Code Re-Activation**
    - Modules affected: Discounts
    - Question: Promo code deleted, then admin wants to reuse the same code name. Is re-creation allowed, or is it blocked as duplicate?
    - Why it matters: Code recycling policy

47. **Pricing Formula Base Storage**
    - Modules affected: Products Management, Pricing Formula
    - Question: price_formula_base stored in product_variants. If formula changes (new admin value), should old products be recalculated?
    - Why it matters: Consistency, historical pricing record

---

### I. NOTIFICATIONS & COMMUNICATION

48. **Email Failure Silent Mode**
    - Modules affected: Notifications, All other modules
    - Question: Email (Resend) failures don't block main flow. Should there be a separate "failed emails" queue for retry, or is it truly fire-and-forget?
    - Why it matters: Email delivery guarantee, compliance

49. **Notification Persistence**
    - Modules affected: Notifications
    - Question: admin_notifications created for every event. Should old "completed" notifications auto-purge after X days, or retained forever?
    - Why it matters: Database growth, audit trail length

50. **Admin Notification SSE Heartbeat Conflict**
    - Modules affected: Notifications
    - Question: Both admin_notifications/sse and custom_requests/sse use SSE. Can admin tab manage both simultaneously?
    - Why it matters: Browser tab/connection management, complexity

51. **Payment Resubmitted Auto-Complete**
    - Modules affected: Notifications
    - Question: Old payment_submitted automatically marked completed when payment_resubmitted created. Should message indicate this in UI?
    - Why it matters: Admin UX, notification clarity

---

### J. CONTENT & SYSTEM SETTINGS

52. **System Settings Cache Invalidation**
    - Modules affected: Content Management, All modules reading settings
    - Question: System settings (bank account, paint coefficients) cached? If yes, how is invalidation communicated to all app instances on Railway?
    - Why it matters: Configuration consistency, cache strategy

53. **Markdown Editor**
    - Modules affected: Content Management
    - Question: Static pages edited as Markdown. Should front-end render Markdown, or back-end pre-render to HTML?
    - Why it matters: Rendering responsibility, XSS prevention

54. **Custom Case Image Dimensions**
    - Modules affected: Content Management
    - Question: Case image (showcase) — is there a recommended image size/aspect ratio, or "use as uploaded"?
    - Why it matters: Frontend display consistency

55. **Surcharge Category Names**
    - Modules affected: Content Management, Pricing
    - Question: Surcharge categories (人物數量, 照片類型) — are these fixed, or can admin create new categories?
    - Why it matters: Customization extent, data validation

---

### K. UPLOAD & EXTERNAL SERVICES

56. **Firebase Service Account Scope**
    - Modules affected: Upload, Production, Custom Requests
    - Question: Firebase Admin SDK (Service Account) has what permissions? Read/write/delete on all buckets?
    - Why it matters: Security, principle of least privilege

57. **File Size Limits Enforcement**
    - Modules affected: Upload
    - Question: 10MB limit for custom photos — is this enforced by Firebase (metadata check), browser (pre-upload validation), or backend (reject on URL)?
    - Why it matters: Consistency, attack surface

58. **Filename Sanitization**
    - Modules affected: Upload, Production
    - Question: User-uploaded filenames — sanitize before Firebase path? Risk of path traversal?
    - Why it matters: Security, path collision prevention

59. **ECpay Integration Credentials**
    - Modules affected: Webhooks, Orders
    - Question: ECpay merchant ID, API key, logistics service codes — where stored? Environment variables?
    - Why it matters: Security, deployment configuration

60. **ECpay Webhook Replay Protection**
    - Modules affected: Webhooks
    - Question: CheckMacValue verification is in place. Is there a nonce/timestamp to prevent replay attacks?
    - Why it matters: Security, duplicate prevention

61. **Resend Email Sender**
    - Modules affected: Notifications, All email-sending modules
    - Question: Resend email from (e.g., noreply@paintlearn.com) — should this be environment-specific (staging vs. prod)?
    - Why it matters: Testing without polluting customer email

---

### L. DATA INTEGRITY & EDGE CASES

62. **Concurrent Order Creation Race**
    - Modules affected: Orders, Color Management
    - Question: Two users simultaneously order same variant with limited stock (e.g., 1 unit left). Both try to take last unit. How is this handled?
    - Why it matters: Overselling prevention, SELECT FOR UPDATE usage

63. **Production Job Approval Idempotency**
    - Modules affected: Production System
    - Question: Approve endpoint can be called multiple times. Is idempotent (no harm re-approving), or rejected as "already approved"?
    - Why it matters: State machine clarity, accidental re-approvals

64. **Order Status Timeline Validation**
    - Modules affected: Orders
    - Question: Can admin force status backward (e.g., processing → pending_payment)? Or only forward transitions allowed?
    - Why it matters: State machine strictness, business rule enforcement

65. **Coupon Scope Across Users**
    - Modules affected: Discounts
    - Question: If one user rejects coupon offer, is it marked globally unavailable, or per-user? (Spec says per-user.)
    - Why it matters: Marketing strategy, promotional budget tracking

66. **Refund Partial vs. Full Ambiguity** [已解決]
    - Modules affected: Orders
    - Answer: Partial refund → `status = partially_refunded`（不維持 completed）. Full refund → `status = refunded`. ENUM updated in schema.md.

67. **Production Progress for Catalog Items**
    - Modules affected: Orders, Production System
    - Question: Catalog items skip in_production status. What if admin later needs to track manufacturing status? Hard to backtrack?
    - Why it matters: Flexibility, reporting coverage

---

### M. TESTING & DEPLOYMENT

68. **Test Database Strategy**
    - Modules affected: All
    - Question: Dedicated test PostgreSQL on Railway, or separate local Docker image? How are migrations tested?
    - Why it matters: Test reliability, environment parity

69. **Load Testing Targets**
    - Modules affected: All
    - Question: What's the expected concurrent user load? Affects capacity planning (SAM model, Celery workers).
    - Why it matters: Infrastructure sizing, bottleneck identification

70. **Logging & Monitoring**
    - Modules affected: All
    - Question: Centralized logging (e.g., Sentry, CloudWatch)? Or just Railway built-in logs?
    - Why it matters: Debugging production issues, performance monitoring

71. **Database Backup Strategy**
    - Modules affected: All
    - Question: Railway managed PostgreSQL — are automatic backups enabled? Restore procedure?
    - Why it matters: Disaster recovery, data loss prevention

---

### N. BUSINESS LOGIC AMBIGUITIES

72. **Free Shipping Quantity Interpretation** [已解決]
    - Modules affected: Orders
    - Answer: "3 件" = total quantity across ALL order_items combined (Σ quantity ≥ 3). Not distinct variants.

73. **Preorder Shipping Preference UI**
    - Modules affected: Orders, Shipping
    - Question: "合併出貨 vs 分開出貨" — when should this choice be presented? At checkout, or after cart review?
    - Why it matters: UX flow, decision timing

74. **Quote Token Validity Across Sessions**
    - Modules affected: Custom Requests
    - Question: Quote email includes token link. If customer doesn't click link until after 1 day but can extend once, does extend reset the 1-day clock?
    - Why it matters: Customer fairness, token lifecycle

75. **In-Progress Order Blocking**
    - Modules affected: Products Management
    - Question: "Don't delete product if in-progress orders exist" — does "in-progress" mean any status except completed/cancelled/refunded?
    - Why it matters: Data integrity, product retirement safety

---

### O. FEATURE SCOPE & PRIORITIES

76. **Variant Availability Display**
    - Modules affected: Products Browsing
    - Question: Should unavailable variants be hidden, disabled (grayed out), or shown with "out of stock" label?
    - Why it matters: UX clarity, inventory communication

77. **Search Autocomplete**
    - Modules affected: Products Browsing
    - Question: Is autocomplete search suggestion expected, or just full-page search results?
    - Why it matters: UX polish, implementation effort

78. **Bulk Operations**
    - Modules affected: Products Management, Orders, Colors
    - Question: Any bulk endpoints needed (e.g., bulk product status update, bulk coupon issuance)? Or are single-item operations sufficient?
    - Why it matters: Admin efficiency, API design

79. **Admin Role Subdivisions**
    - Modules affected: Auth, All admin modules
    - Question: Spec says "all admins have same permissions initially." Should permission model be designed to support future subdivision (e.g., inventory admin, customer service admin)?
    - Why it matters: Architecture extensibility, access control model

80. **Customer Service Portal**
    - Modules affected: Orders, Notifications
    - Question: Is there a customer service admin panel separate from merchant admin? (Spec silent on this.)
    - Why it matters: Team role separation, feature scope

---

### P. LEGAL & COMPLIANCE

81. **GDPR / Data Privacy**
    - Modules affected: Users, Orders, Custom Requests
    - Question: Should there be data export / deletion endpoints for customer privacy requests?
    - Why it matters: Legal compliance, customer rights

82. **Refund Policy Storage**
    - Modules affected: Content Management
    - Question: Refund policy is editable by admin. Should change history be tracked, or overwrite?
    - Why it matters: Dispute resolution, liability

---

## SUMMARY OF CRITICAL DECISIONS NEEDED

**Tier 1 (Blocks Implementation Start):**
- #1: Database type confirmation
- #2: Deployment platform finalization
- #25: Preorder fulfillment logic (per-color vs per-item)
- #62: Concurrent order stock race condition handling

**Tier 2 (Affects Design Significantly):**
- #3: Frontend framework (impacts CORS, session handling)
- #6: OAuth decision
- #35: Payment confirmation SLA
- #48: Email retry strategy
- #72: Free shipping logic clarification

**Tier 3 (Nice to Know Before Full Implementation):**
- All others; can be decided during sprint planning or module-by-module