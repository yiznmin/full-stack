# 後端實作規劃

> 每個模組實作前必須對照 schema.md 與 api.md 確認完整性，確認無誤後才開始寫程式碼。

---

## OUTPUT 1: IMPLEMENTATION PLAN

### Module 1: Auth (Users, Email Verification, Password Reset)

**Files to Create:**
- `auth/router.py` - Endpoints for register, login, logout, email verification, password reset
- `auth/service.py` - Auth logic: token generation, password hashing, email sending
- `auth/models.py` - User, EmailVerificationToken, PasswordResetToken ORM models
- `auth/schemas/request.py` - RegisterRequest, LoginRequest, VerifyEmailRequest, ResetPasswordRequest
- `auth/schemas/response.py` - UserResponse, AuthTokenResponse

**DB Tables Involved:**
- `users` (id, name, email, password_hash, gender, birthday, role, is_active, is_email_verified, pending_email, created_at, updated_at)
- `email_verification_tokens` (id, user_id, token, token_type, expires_at, used_at, created_at)
- `password_reset_tokens` (id, user_id, token, expires_at, used_at, created_at)

**API Endpoints Covered:**
- POST /auth/register
- POST /auth/login
- POST /auth/logout
- GET /auth/me
- POST /auth/verify-email
- POST /auth/resend-verification
- POST /auth/forgot-password
- POST /auth/reset-password
- POST /admin/auth/login
- POST /admin/auth/logout
- POST /admin/auth/forgot-password

**Key Business Logic:**
- Password validation (min 10 chars, alphanumeric mix)
- Name validation (min 4 UTF-8 chars)
- Email uniqueness check, including pending_email
- Token generation and hashing (use bcrypt or similar)
- Email verification triggers new_user coupon issuance
- Email change verification: pending_email → email after verification
- Password reset: auto-expire all unused tokens, allow 1-hour reset window
- Account deactivation: check is_active on every request

**Dependencies:**
- External: Resend (email service)
- Internal: coupon module (for new_user voucher issuance)
- Internal: Firebase (for signed URLs in emails)

**Potential Conflicts:**
- JWT token management must coordinate with other modules on cookie settings
- Email service failures should not block main flow (log warning only)

---

### Module 2: User Profile + Shipping Profiles

**Files to Create:**
- `users/router.py` - Endpoints for user profile update, shipping profiles CRUD
- `users/service.py` - Profile update logic, shipping profile management
- `users/models.py` - ShippingProfile ORM model
- `users/schemas/request.py` - UpdateUserRequest, CreateShippingProfileRequest
- `users/schemas/response.py` - UserDetailResponse, ShippingProfileResponse

**DB Tables Involved:**
- `users` (for profile updates)
- `shipping_profiles` (id, user_id, shipping_type, recipient_name, phone, email, city, district, address_detail, store_id, store_name, is_default, created_at)

**API Endpoints Covered:**
- PATCH /users/me
- POST /users/me/change-password
- POST /users/me/request-email-change
- GET /users/me/shipping-profiles
- POST /users/me/shipping-profiles
- PUT /users/me/shipping-profiles/{id}
- DELETE /users/me/shipping-profiles/{id}
- PATCH /users/me/shipping-profiles/{id}/set-default

**Key Business Logic:**
- Only one is_default=true per user; auto-cancel old default when setting new
- Validate shipping_type-specific required fields (home vs supermarket)
- Email change request stores new email in pending_email
- Password change requires old password verification
- Constraint: cannot change role (customer only, admin must use admin endpoint)

**Dependencies:**
- Auth module (for current user context)
- External: city/district mapping data (Taiwan administrative divisions)

**Potential Conflicts:**
- Shipping profile deletion must check if used in pending/processing orders
- Email change conflicts with existing emails or pending_emails

---

### Module 3: Products (Public Browsing)

**Files to Create:**
- `products/router.py` - Public endpoints for browsing, search, details
- `products/service.py` - Product query logic, filtering, search with PostgreSQL ILIKE
- `products/models.py` - Product, ProductVariant, ProductImage, Tag, ProductTag, ProductSeries ORM models
- `products/schemas/request.py` - ProductFilterRequest (for query params)
- `products/schemas/response.py` - ProductCardResponse, ProductDetailResponse, ProductSearchResponse, VariantResponse

**DB Tables Involved:**
- `products` (id, title, description, cover_image_url, series_id, series_order, status, created_at, updated_at)
- `product_variants` (id, product_id, production_job_id, price, price_formula_base, is_active, created_at)
- `product_images` (id, product_id, image_url, sort_order, created_at)
- `product_series` (id, name, description, created_at)
- `tags` (id, name, created_at)
- `product_tags` (product_id, tag_id)
- `production_jobs` (for variant specs: difficulty, detail, canvas_w_cm, canvas_h_cm, num_colors_used, filled_template_url)
- `palette_color_mappings` (for stock calculation: physical_color_id, required_ml)
- `physical_colors` (stock_ml, is_active)

**API Endpoints Covered:**
- GET /products (with filters: difficulty, detail, canvas_size, tag_id, series_id, sort, pagination)
- GET /products/search (with keyword search across title, description, tags)
- GET /products/{id} (with variants, images, series, tags)
- GET /products/{id}/related (same series products)
- GET /tags

**Key Business Logic:**
- Calculate price_min/price_max from all variant prices
- Determine is_preorder based on stock_ml of all physical_colors used
- Join with production_jobs to get variant specs (difficulty, detail, canvas dimensions)
- Stock check: if any physical_color used has stock_ml=0 or is_active=false, mark is_preorder=true
- Pagination: 24 items per page

**Dependencies:**
- Production module (for job specs and filled_template_url)
- Color module (for stock checks)

**Potential Conflicts:**
- must handle product.status='draft' or 'off_sale' - exclude from public listing
- variant.is_active=false should be excluded or marked unavailable

---

### Module 4: Products Management (Admin)

**Files to Create:**
- `admin_products/router.py` - Admin product CRUD endpoints
- `admin_products/service.py` - Product creation, variant management, series management, tags
- `admin_products/models.py` (shares models with Module 3, can import)
- `admin_products/schemas/request.py` - CreateProductRequest, UpdateProductRequest, CreateVariantRequest
- `admin_products/schemas/response.py` - AdminProductResponse, AdminVariantResponse

**DB Tables Involved:**
- `products`, `product_variants`, `product_images`, `product_series`, `tags`, `product_tags`, `production_jobs`

**API Endpoints Covered:**
- GET /admin/products (search, status filter, pagination)
- POST /admin/products (create with basic info)
- PUT /admin/products/{id} (update)
- DELETE /admin/products/{id} (soft delete via status=off_sale check)
- POST /admin/products/{id}/images (add image)
- DELETE /admin/products/{id}/images/{image_id}
- PATCH /admin/products/{id}/images/reorder
- POST /admin/products/{id}/variants (from approved production_job)
- PATCH /admin/products/{id}/variants/{variant_id} (update price, is_active)
- DELETE /admin/products/{id}/variants/{variant_id}
- GET /admin/series
- POST /admin/series
- PUT /admin/series/{id}
- DELETE /admin/series/{id} (check no products before delete)
- GET /admin/tags
- POST /admin/tags
- PUT /admin/tags/{id}
- DELETE /admin/tags/{id} (CASCADE delete product_tags)

**Key Business Logic:**
- CREATE variant: fetch production_job (approved=true), calculate price_formula_base from pricing formula, allow manual override
- UPDATE variant: UNIQUE(product_id, production_job_id) with ON CONFLICT UPDATE for price/is_active
- DELETE product: must be off_sale AND no in-progress orders
- Series: delete blocked if products still associated
- Tags: deletion cascades to product_tags
- Images: maintain sort_order; reorder via array of image_ids

**Dependencies:**
- Production module (to fetch approved production_jobs)
- Pricing formula module (for price calculation)
- Orders module (to check in-progress orders before deletion)

**Potential Conflicts:**
- Variant creation must validate production_job.approved=true and color mappings complete
- Price formula calculation logic must align with pricing_formula.md

---

### Module 5: Production System (Admin)

**Files to Create:**
- `admin_production/router.py` - Image upload, job creation, approval, post-processing, SAM mask
- `admin_production/service.py` - Job management, Celery task queueing, SAM integration, post-processing
- `admin_production/models.py` - Image, ProductionJob, PaletteColorMapping ORM models
- `admin_production/schemas/request.py` - CreateProductionJobRequest, SAMMaskRequest, PostProcessRequest
- `admin_production/schemas/response.py` - JobDetailResponse, ImageResponse

**DB Tables Involved:**
- `images` (id, uploader_id, original_url, filename, width, height, created_at)
- `production_jobs` (id, image_id, custom_request_id, status, approved, detail, difficulty, mode, canvas_w_cm, canvas_h_cm, params..., palette_json, approved_at, batch_id, created_at)
- `palette_color_mappings` (id, production_job_id, template_id, algorithm_rgb, physical_color_id, required_ml, mapped_by, created_at, updated_at)
- `physical_colors` (for availability check and required_ml calculation)
- `custom_requests` (for photo_url retrieval)

**API Endpoints Covered:**
- GET /admin/images
- POST /admin/images (store metadata, actual file uploaded to Firebase before this)
- POST /admin/production/jobs (create single or batch)
- GET /admin/production/jobs (list with filters: status, approved, batch_id, image_id, custom_request_id, pagination)
- GET /admin/production/jobs/{id} (with palette_mappings, filled_template_url, etc.)
- GET /admin/production/jobs/{id}/signed-url (for private files: svg, snapped_rgb)
- POST /admin/production/jobs/{id}/post-process/merge-color
- POST /admin/production/jobs/{id}/post-process/eliminate-border
- POST /admin/production/jobs/{id}/post-process/smooth-contour
- POST /admin/production/jobs/{id}/sam-mask
- POST /admin/production/jobs/{id}/approve
- GET /admin/production/jobs/{id}/export-pdf

**Key Business Logic:**
- Accept image_id or custom_request_id (not both simultaneously from different sources)
- Create Celery tasks with batch_id grouping; queue sequentially (one at a time)
- SAM model lazy-load on first request (5-10sec cold start)
- Store sam_points, polygons, mask_url on job; recalculate mask_coverage as percentage
- On failure: on_failure callback deletes all Firebase uploads recorded in task context
- Post-process operations: modify snapped_rgb, regenerate SVG, update filled_template, set approved=false
- Approve endpoint: set approved=true, store notes, record approved_at timestamp
- PDF export: fetch SVG, expand 5cm border, call Inkscape, return binary (no storage)
- Private file access: generate signed URLs via Firebase Admin SDK (15min TTL)

**Dependencies:**
- Color module (for physical_color data, required_ml calculation)
- Orders module (for context when job links to orders)
- External: Firebase Storage (file operations)
- External: Celery (task queue)
- External: Inkscape CLI (PDF conversion)
- External: SAM model (via Celery worker or FastAPI endpoint in same service)

**Potential Conflicts:**
- Batch job sequencing must prevent SAM model OOM from concurrent loads
- on_failure cleanup must be reliable; partial cleanup could orphan files
- Approved status and color mapping completion must be coordinated

---

### Module 6: Color Management + Palette Mapping (Admin)

**Files to Create:**
- `admin_colors/router.py` - Color CRUD, stock updates, shortage dashboard
- `admin_colors/service.py` - Color management, palette mapping, required_ml calculation, preorder fulfillment
- `admin_colors/models.py` (shares models with production, can import)
- `admin_colors/schemas/request.py` - CreateColorRequest, UpdateStockRequest
- `admin_colors/schemas/response.py` - ColorResponse, ShortageColorResponse
- `admin_palette/router.py` - Palette mapping UI endpoints
- `admin_palette/service.py` - Mapping logic, LAB color distance, copy mappings, complete mappings
- `admin_palette/schemas/request.py` - UpdateMappingRequest, CopyMappingsRequest, CompleteMappingsRequest
- `admin_palette/schemas/response.py` - MappingDetailResponse, RequiredMlResponse

**DB Tables Involved:**
- `physical_colors` (id, code, name, color_family, brand, rgb, stock_ml, is_active, created_at, updated_at)
- `palette_color_mappings` (id, production_job_id, template_id, algorithm_rgb, physical_color_id, required_ml, mapped_by, created_at, updated_at)
- `production_jobs` (palette_json, num_colors_used)
- `orders`, `order_items` (for preorder fulfillment check)

**API Endpoints Covered:**
- GET /admin/colors (search, filter by color_family, is_active)
- POST /admin/colors (create new color)
- PUT /admin/colors/{id} (update color info)
- PATCH /admin/colors/{id}/toggle-active (set is_active)
- PATCH /admin/colors/{id}/stock (update stock_ml, trigger preorder scan)
- GET /admin/colors/shortage-dashboard (show colors with stock_ml < required_ml)
- GET /admin/production/jobs/{id}/palette-mappings
- PUT /admin/production/jobs/{id}/palette-mappings/{template_id} (change physical_color)
- POST /admin/production/jobs/{id}/palette-mappings/copy-from/{source_job_id}
- POST /admin/production/jobs/{id}/palette-mappings/complete (mark done, calculate required_ml)

**Key Business Logic:**
- LAB color distance calculation: convert RGB to LAB, find nearest physical_color (Euclidean distance in LAB space), use physical_color.id as tiebreaker
- Auto-mapping: on entering palette mapping UI, suggest system defaults; marked_by='system'
- required_ml formula: max(canvas_area_cm2 × color_percent × paint_ml_per_cm2 × paint_buffer_ratio, paint_min_ml)
  - Coefficients from system_settings: paint_ml_per_cm2, paint_min_ml, paint_buffer_ratio
- Stock update flow: 
  1. Increment stock_ml by add_ml
  2. Query order_items with preorder_qty > 0 and using this color
  3. For each preorder order (ordered by created_at), check if stock_ml >= required_ml × preorder_qty
  4. If yes: fulfilled_qty += preorder_qty, preorder_qty = 0, decrement stock_ml
  5. If all order_items in order are fulfilled and shipping_preference='separate', trigger automatic shipment creation
  6. Email customer about preorder fulfillment
  7. Create admin_notification (stock_shortage resolved)
- Shortage dashboard: for each color, calculate total required_ml across all preorder orders; show shortage_ml = required_ml - stock_ml (only if > 0)
- Copy mappings: fetch source job's palette_color_mappings, copy by template_id to target job, still require manual confirmation
- Complete mappings: lock all mappings, calculate required_ml for each, check stock_ml availability

**Dependencies:**
- Production module (for production_job and palette_json)
- Orders module (for preorder order queries)
- System settings module (for paint coefficients)
- External: color science library for RGB↔LAB conversion

**Potential Conflicts:**
- Preorder fulfillment must use SELECT FOR UPDATE on physical_colors to prevent race conditions
- Required_ml calculation must match pricing formula logic for consistency
- Palette mapping completion should block if any color has zero stock but is_active=true

---

### Module 7: Cart

**Files to Create:**
- `cart/router.py` - Cart endpoints
- `cart/service.py` - Cart item management, checkout preview
- `cart/models.py` - CartItem ORM model
- `cart/schemas/request.py` - AddToCartRequest, UpdateCartItemRequest, CheckoutPreviewRequest
- `cart/schemas/response.py` - CartResponse, CartItemResponse, CheckoutPreviewResponse

**DB Tables Involved:**
- `cart_items` (id, user_id, product_variant_id, quantity, created_at)
- `product_variants` (price, is_active)
- `production_jobs` (for variant specs)

**API Endpoints Covered:**
- GET /cart
- POST /cart/items (add to cart)
- PATCH /cart/items/{id} (update quantity)
- DELETE /cart/items/{id}
- POST /cart/checkout-preview (preview without creating order)

**Key Business Logic:**
- Only authenticated users can use cart
- Add item: check variant.is_active; if false, return 409
- Get cart: fetch current prices from product_variants (not snapshot); calculate subtotal
- Get variants' stock by joining to production_job → palette_color_mappings → physical_colors; sum up available stock_ml
- Checkout preview: calculate subtotal, apply discount logic (see discount section), calculate shipping, sum total
  - Discount priority: public_code (if provided) > user_coupon (if provided) > auto_checkout (best one)
  - Shipping: check if subtotal >= 800 OR total quantity >= 3; if yes, free; else charge based on shipping_type
  - Return split_items with fulfilled_qty and preorder_qty
- No price snapshots stored in cart; prices are live from product_variants

**Dependencies:**
- Products module (for variant data)
- Production module (for stock calc)
- Discount module (for coupon/auto_checkout logic)
- Orders module (for shipping fee logic)

**Potential Conflicts:**
- Variant deletion or status change affects cart display
- Stock calculation must be fast (consider caching or index optimization)

---

### Module 8: Orders (Customer)

**Files to Create:**
- `orders/router.py` - Customer order endpoints (list, detail, cancel, payment submission, confirm received)
- `orders/service.py` - Order creation, cancellation, payment handling, status transitions
- `orders/models.py` - Order, OrderItem, Shipment, ProductionProgress, PaymentSubmission ORM models (shares with admin orders)
- `orders/schemas/request.py` - CreateOrderRequest, PaymentSubmissionRequest, CancelOrderRequest, ConfirmReceivedRequest
- `orders/schemas/response.py` - OrderResponse, OrderListResponse, OrderDetailResponse, ShipmentResponse, ProductionProgressResponse

**DB Tables Involved:**
- `orders` (id, order_number, user_id, status, subtotal, discount_amount, discount_source, shipping_fee, total, user_coupon_id, shipping_type, shipping_preference, shipping_snapshot, payment_deadline, paid_at, completed_at, cancel_reason, refund_amount, refunded_at, customer_notes, admin_notes, created_at, updated_at)
- `order_items` (id, order_id, product_variant_id, custom_request_id, production_job_id, product_title_snapshot, variant_spec_snapshot, unit_price, quantity, fulfilled_qty, preorder_qty)
- `shipments` (id, order_id, shipment_type, status, tracking_number, ecpay_logistics_id, shipped_at, delivered_at, created_at)
- `production_progress` (id, order_item_id, status, notes, updated_at, created_at)
- `payment_submissions` (id, order_id, is_flagged, transfer_amount, transfer_date, transfer_time, account_last5, notes, created_at)
- `cart_items` (for source items)
- `user_coupons` (for coupon application)
- `physical_colors` (for stock deduction)
- `palette_color_mappings` (for required_ml lookup)

**API Endpoints Covered:**
- POST /orders (create order from checkout; SELECT FOR UPDATE on physical_colors for stock deduction)
- GET /orders (list with status filter, pagination)
- GET /orders/{id} (detail view)
- POST /orders/{id}/payment-submission (customer fills payment info)
- POST /orders/{id}/confirm-received (customer marks shipment delivered)
- POST /orders/{id}/cancel (cancel pending_payment order)

**Key Business Logic:**
- CREATE order:
  1. Validate all cart items: is_active=true, stock available
  2. Calculate subtotal from current product_variants.price × quantity
  3. Calculate discount (from discount module)
  4. Calculate shipping based on shipping_type and free shipping conditions
  5. SELECT FOR UPDATE on all physical_colors used in order_items
  6. Deduct stock_ml from physical_colors (fulfilled_qty portion only)
  7. Calculate fulfilled_qty and preorder_qty for each order_item based on available stock
  8. Create order with status=pending_payment, payment_deadline=now()+24h
  9. Create shipment record(s) with status=pending
  10. Clear cart_items for this user
  11. Send order confirmation email with payment details
  12. Generate order_number via PostgreSQL SEQUENCE (global, always incrementing)
- Order number format: PL-YYYYMMDD-XXXXXX (date of creation, 6-digit sequence)
- CANCEL order (pending_payment only):
  1. SELECT FOR UPDATE on order
  2. Check status is pending_payment
  3. Revert stock_ml for all physical_colors (fulfilled_qty portion)
  4. If user_coupon used: revert is_used=false
  5. Set status=cancelled, record cancel_reason
  6. Send cancellation email
- PAYMENT SUBMISSION:
  1. Store transfer info in payment_submissions
  2. Create admin_notification (payment_submitted)
  3. If is_flagged already set, also create payment_resubmitted notification
- CONFIRM RECEIVED:
  1. Only valid if order.status=shipped AND all shipments.status=shipped
  2. Set shipment.status=delivered, delivered_at=now()
  3. If all shipments delivered, set order.status=completed
  4. Trigger reward coupon issuance (spend_reward, returning_loyal)
  5. Send completion email

**Dependencies:**
- Cart module (for items source)
- Products module (for variant info)
- Production module (for job specs)
- Color module (for stock deduction)
- Discount module (for coupon/auto_checkout logic)
- Coupon module (for coupon handling, reward issuance)
- Notifications module (for email, admin alerts)
- External: Resend (emails)

**Potential Conflicts:**
- Stock deduction must be atomic (SELECT FOR UPDATE mandatory)
- Order number generation must be globally unique (SEQUENCE across all nodes)
- Discount and shipping logic must align with cart preview logic

---

### Module 9: Orders Management (Admin)

**Files to Create:**
- `admin_orders/router.py` - Admin order management endpoints
- `admin_orders/service.py` - Order status transitions, shipment creation, refund handling, payment flag
- (shares ORM models with Module 8)
- `admin_orders/schemas/request.py` - UpdateOrderStatusRequest, CreateShipmentRequest, RefundOrderRequest, FlagPaymentRequest
- `admin_orders/schemas/response.py` - AdminOrderDetailResponse, ShipmentDetailResponse

**DB Tables Involved:**
- All order-related tables from Module 8
- `system_settings` (for bank account info)

**API Endpoints Covered:**
- GET /admin/orders (search by order_number/customer name/email, filter by status/date/order_type, pagination)
- GET /admin/orders/{id} (full detail for admin)
- PATCH /admin/orders/{id}/status (manual status transition)
- POST /admin/orders/{id}/shipments (create shipment via ECpay API)
- PATCH /admin/orders/{id}/production-progress/{progress_id} (update production status)
- POST /admin/orders/{id}/refund (initiate refund)
- PATCH /admin/orders/{id}/payment-submissions/{sub_id}/flag (mark payment info incorrect)
- PATCH /admin/orders/{id}/admin-notes (update admin-only notes)

**Key Business Logic:**
- STATUS TRANSITIONS (SELECT FOR UPDATE):
  - paid: confirm payment, send email, create production_progress records (status=pending for each order_item)
  - processing: in production/manufacturing
  - shipped: trigger ECpay shipment (API call), on success auto-update shipments.status=shipped, increment production_progress to shipped
  - completed: (auto from Webhook or customer confirm, or manual here)
  - refund_processing / refunded: manage refund flow
- SHIPMENT CREATION:
  1. Call ECpay API with shipping_snapshot and shipping_type
  2. On success: shipments.status=shipped, shipped_at=now(), tracking_number populated
  3. Send tracking email to customer
  4. Update all associated production_progress.status=shipped
  5. Check if all shipments delivered; if yes, order.status=completed
  6. On ECpay failure: return 503, do not change order state
- PRODUCTION PROGRESS:
  1. Auto-created when order.status→paid (for each order_item, initial status=pending)
  2. Transitions: pending → in_production (custom only) → manufacturing → packaging → ready_to_ship → shipped
  3. Each transition sends email to customer (except pending, packaging)
  4. Admin can update status via dedicated endpoint
- PAYMENT FLAG:
  1. Set payment_submissions.is_flagged=true
  2. Recalculate payment_deadline = now() + 24h
  3. Send email to customer to resubmit
  4. Create payment_resubmitted notification (auto-complete old payment_submitted)
- REFUND:
  1. Validate order.status (typically paid/processing/shipped/completed)
  2. If refund_amount < total: status stays completed, record refund_amount
  3. If refund_amount = total: status=refunded
  4. Revert stock_ml for all fulfilled_qty (not preorder_qty)
  5. If user_coupon used: revert is_used=false
  6. If spend_reward/returning_loyal sourced from this order: set expires_at=now() on unspent coupons
  7. Send refund email

**Dependencies:**
- Orders module (shares models and logic)
- Production module (for progress tracking)
- Color module (for stock reversion)
- Coupon module (for coupon handling in refunds)
- Notifications module (for emails and admin alerts)
- External: ECpay API (shipment creation)
- External: Resend (emails)
- External: Celery Beat (automatic payment expiration, shipment overdue checks)

**Potential Conflicts:**
- ECpay API failures must not corrupt order state
- Concurrent refund and payment confirmation must be serialized
- Coupon reversion logic must account for multiple reward types

---

### Module 10: Custom Requests (Customer + Admin)

**Files to Create:**
- `custom_requests/router.py` - Customer custom request endpoints (create, list, detail, messages, photo, SSE)
- `custom_requests/service.py` - Request lifecycle, message system, SSE logic
- `custom_requests/models.py` - CustomRequest, CustomRequestMessage ORM models
- `custom_requests/schemas/request.py` - CreateCustomRequestRequest, SendMessageRequest, UpdatePhotoRequest
- `custom_requests/schemas/response.py` - CustomRequestResponse, MessageResponse
- `admin_custom_requests/router.py` - Admin custom request endpoints (manage requests, quote, messages, photo signed URL, SSE)
- `admin_custom_requests/service.py` - Quotation logic, production job creation for custom
- `admin_custom_requests/schemas/request.py` - SendQuoteRequest, MarkNegotiatingRequest, MessageRequest
- `admin_custom_requests/schemas/response.py` - AdminCustomRequestResponse

**DB Tables Involved:**
- `custom_requests` (id, user_id, request_type, status, photo_url, ref_product_id, canvas_w_cm, canvas_h_cm, difficulty, detail, customer_notes, quoted_price, quote_token, quote_expires_at, is_extended, parent_request_id, order_id, admin_notes, created_at, quoted_at)
- `custom_request_messages` (id, request_id, sender_type, message, created_at)
- `custom_photo_prices` (canvas_w, canvas_h, difficulty, price)
- `custom_photo_surcharges` (id, category, label, amount, is_active)
- `production_jobs` (for job creation when custom request is approved)
- `orders` (for order creation after quote confirmation)

**API Endpoints Covered:**
- POST /custom-requests (create custom request)
- GET /custom-requests (list with status filter, pagination)
- GET /custom-requests/{id} (detail with messages)
- POST /custom-requests/{id}/messages (customer sends message)
- PATCH /custom-requests/{id}/photo (replace photo, delete old from Firebase)
- GET /custom-requests/{id}/sse (customer SSE stream)
- GET /custom/quote/{token} (quote confirmation page)
- POST /custom/quote/{token}/confirm (confirm quote, create order)
- POST /custom/quote/{token}/reject (reject quote, record reason)
- POST /custom/quote/{token}/extend (extend quote by 1 day, once per request)
- GET /admin/custom-requests (admin list with filters)
- GET /admin/custom-requests/{id} (admin detail view)
- PATCH /admin/custom-requests/{id}/mark-negotiating (change status)
- POST /admin/custom-requests/{id}/quote (send quote)
- POST /admin/custom-requests/{id}/messages (admin sends message)
- GET /admin/custom-requests/{id}/photo-signed-url (get private photo URL)
- GET /admin/custom-requests/sse (admin SSE stream)

**Key Business Logic:**
- CREATE request:
  1. Validate request_type (custom_photo or custom_spec)
  2. For custom_photo: photo_url required, upload to Firebase private storage
  3. For custom_spec: ref_product_id optional
  4. Set status=quote_pending
  5. Auto-send welcome message (sender_type=admin)
  6. Create admin_notification (quote_pending, requires_action=true)
  7. Return request id
- SEND MESSAGE (customer or admin):
  1. Check if recipient has active SSE connection
  2. If yes: push via SSE (no email)
  3. If no: send email with snippet and link back to page
  4. Create admin_notification (new_message) if customer sends to admin
- UPDATE PHOTO:
  1. Delete old photo_url from Firebase
  2. Upload new photo
  3. Update photo_url
  4. Production jobs referencing this request still work (lazy-load from updated URL)
- SEND QUOTE:
  1. Set status=quote_sent
  2. Generate quote_token (random, hashed for storage)
  3. Set quote_expires_at=now()+1 day
  4. Set quoted_at=now()
  5. Send email with token link and quote details
  6. Add quote message to conversation (via system message)
  7. Create admin_notification (quote_sent, requires_action=false)
- CONFIRM QUOTE:
  1. Validate quote_token (hash and compare)
  2. Check quote_expires_at > now()
  3. Set status=quote_confirmed
  4. Set order_id=null (will create order in next step)
  5. Proceed to checkout (fill shipping, calculate shipping fee, create order)
  6. Order creation: status=pending_payment, marked as custom via custom_request_id in order_items
  7. Return payment info
  8. Create admin_notification (quote_confirmed, requires_action=false)
- REJECT QUOTE:
  1. Set status=quote_rejected
  2. Record reason in custom_request_messages or separate field
  3. Create admin_notification (quote_rejected, requires_action=false)
- EXTEND QUOTE:
  1. Check is_extended=false
  2. Set quote_expires_at += 1 day
  3. Set is_extended=true
  4. Send notification email to admin
  5. Return new expire_at
- MARK NEGOTIATING:
  1. Set status=negotiating (manual admin action, no auto-trigger)
- PHOTO SIGNED URL:
  1. Admin auth required
  2. Generate Firebase signed URL for photo_url (15min TTL)
  3. Return URL
- AUTOMATIC EXPIRATIONS (Celery Beat):
  1. Every 5 min: scan custom_requests with status=quote_sent and quote_expires_at < now()
  2. Set status=quote_expired
  3. Send expiration email to customer
  4. Create admin_notification (quote_expired, requires_action=false)
- SSE CONNECTIONS:
  1. Customer /custom-requests/{id}/sse: push new messages from admin
  2. Admin /admin/custom-requests/sse: push new requests (quote_pending) and messages (new_message)
  3. Heartbeat every 30 sec (Railway keepalive)
  4. Front-end auto-reconnect on disconnect

**Dependencies:**
- Orders module (for quote confirmation → order creation)
- Pricing module (for base price lookup in quotation)
- Production module (for production job creation in custom orders)
- Notifications module (for emails and admin alerts)
- External: Firebase Storage (photo storage/deletion)
- External: Resend (emails)
- External: Celery Beat (quote expiration)
- External: SSE/EventStream (real-time messaging)

**Potential Conflicts:**
- Photo deletion must be reliable; if DELETE fails in Firebase, job proceeds but photo orphans
- Custom request production jobs must link back to request for tracking
- Quote token generation and hashing must use cryptographically secure method

---

### Module 11: Discount System

**Files to Create:**
- `coupons/router.py` - Customer coupon endpoints (list coupons, validate promo code)
- `coupons/service.py` - Coupon evaluation, issuance logic
- `coupons/models.py` - CouponConfig, PromoCode, UserCoupon ORM models
- `coupons/schemas/request.py` - ValidatePromoCodeRequest
- `coupons/schemas/response.py` - CouponResponse, PromoCodeValidationResponse
- `admin_coupons/router.py` - Admin coupon management
- `admin_coupons/service.py` - Coupon config CRUD, manual issuance, auto_checkout logic
- `admin_coupons/schemas/request.py` - CreateCouponConfigRequest, UpdateCouponConfigRequest, IssueCouponsRequest, CreateAutoCheckoutRequest
- `admin_coupons/schemas/response.py` - CouponConfigResponse, UsageStatsResponse

**DB Tables Involved:**
- `coupon_configs` (id, coupon_type, discount_type, discount_value, min_purchase, is_active, params, updated_at)
- `promo_codes` (id, code, discount_type, discount_value, min_purchase, start_at, end_at, max_total_uses, max_per_user, total_used, is_active, created_at, updated_at)
- `user_coupons` (id, user_id, coupon_config_id, promo_code_id, discount_type, discount_value, min_purchase, expires_at, is_used, used_at, used_in_order_id, source_order_id, created_at)
- `orders` (discount_amount, discount_source, auto_checkout_config_id, user_coupon_id)

**API Endpoints Covered:**
- GET /users/me/coupons (list available, used, expired)
- POST /promo-codes/validate (validate public_code for order)
- GET /admin/coupon-configs
- GET /admin/coupon-configs/{id}/usage-stats
- PATCH /admin/coupon-configs/{id}
- POST /admin/coupon-configs/auto-checkout
- DELETE /admin/coupon-configs/{id}
- POST /admin/users/issue-coupons (batch manual issuance)
- GET /admin/promo-codes
- POST /admin/promo-codes
- PUT /admin/promo-codes/{id}
- DELETE /admin/promo-codes/{id}
- GET /admin/user-coupons (query with filters)

**Key Business Logic:**
- COUPON TYPES:
  1. `new_user`: issued on email verification (is_email_verified=true), expires in X days (from params.valid_days)
  2. `spend_reward`: issued when order.status=completed AND order.total >= trigger_threshold, expires in X days
  3. `returning_loyal`: issued when order.status=completed AND order.total >= 1000 AND user has prior completed orders, expires in X days
     - Priority: if both spend_reward and returning_loyal apply, only returning_loyal issued
  4. `public_code`: manually entered at checkout, each has individual code, usage tracked atomically
  5. `manual`: issued by admin, fixed params per issuance
  6. `auto_checkout`: auto-applied at checkout if subtotal >= trigger_threshold AND within date range
- DISCOUNT APPLICATION PRIORITY:
  1. If public_code provided: use it (validate all conditions, increment total_used atomically)
  2. Else if user_coupon_id provided: use it
  3. Else: auto-select best auto_checkout (highest discount_amount)
- COUPON SNAPSHOTS:
  1. When coupon used/applied, snapshot discount_type, discount_value, min_purchase to user_coupons
  2. Later admin changes to coupon_configs don't affect already-issued coupons
- AUTO_CHECKOUT USAGE:
  1. Not a coupon_configs type with max one per type; instead can have multiple (for concurrent promotions)
  2. At checkout, calc discount_amount for each active auto_checkout matching conditions
  3. Only apply the one with max discount_amount
  4. Record auto_checkout_config_id in order, discount_source='auto_checkout'
- REFUND/CANCEL HANDLING:
  1. If order cancelled/refunded and had user_coupon: revert is_used=false
  2. If promo_code used: also decrement promo_codes.total_used (atomic UPDATE)
  3. If spend_reward/returning_loyal sourced from an order that's refunded: expire unspent coupons (expires_at=now())
  4. Not applicable to auto_checkout (no coupon record created)
- PROMO CODE ATOMICITY:
  1. Use: `UPDATE promo_codes SET total_used = total_used + 1 WHERE id = ? AND total_used < max_total_uses`
  2. If affected rows = 0: reject with "code reached limit"
- UNIQUE CONSTRAINTS:
  1. coupon_configs: UNIQUE INDEX on coupon_type WHERE coupon_type != 'auto_checkout'
  2. promo_codes: UNIQUE on code
  3. user_coupons: no unique; same user can have multiple of same config (multi-issuance)

**Dependencies:**
- Orders module (for order completion triggers, refund handling)
- Notifications module (for coupon issuance emails, if needed)
- System settings module (for coupon validity dates)

**Potential Conflicts:**
- Promo code total_used increment must be atomic (race condition without proper DB lock)
- Coupon expiration checking must happen at order-time, not pre-calculate
- auto_checkout and user_coupon logic must be correctly prioritized in checkout

---

### Module 12: Notifications (SSE)

**Files to Create:**
- `notifications/router.py` - Admin notification list, status update, SSE stream, bulk complete
- `notifications/service.py` - Notification creation, status transitions, SSE broadcast
- `notifications/models.py` - AdminNotification ORM model
- `notifications/schemas/request.py` - UpdateNotificationStatusRequest, BulkCompleteRequest
- `notifications/schemas/response.py` - AdminNotificationResponse, NotificationListResponse

**DB Tables Involved:**
- `admin_notifications` (id, type, requires_action, status, reference_type, reference_id, message, created_at, updated_at)

**API Endpoints Covered:**
- GET /admin/notifications (list with filters: status, requires_action, pagination)
- GET /admin/notifications/sse (SSE stream for real-time push)
- PATCH /admin/notifications/{id}/status (update status)
- PATCH /admin/notifications/bulk-complete (batch mark completed)

**Key Business Logic:**
- NOTIFICATION TYPES & CREATION TRIGGERS:
  | Type | requires_action | Trigger |
  | --- | --- | --- |
  | quote_pending | true | custom_requests created |
  | custom_order_paid | true | custom order status → paid |
  | new_message | true | customer message in custom request |
  | payment_submitted | true | customer fills payment_submissions |
  | payment_resubmitted | true | customer refills (auto-complete old payment_submitted) |
  | shipment_overdue | true | shipped 14+ days without delivery (Celery Beat daily) |
  | stock_shortage | true | color stock still insufficient after update |
  | order_cancelled | false | customer cancels order |
  | quote_confirmed | false | customer confirms quote |
  | quote_rejected | false | customer rejects quote |
  | ecpay_status | false | ECpay webhook with intermediate status |
  
- STATUSES: unhandled (new), in_progress (admin acknowledged), completed (resolved)
- SSE STREAM:
  1. Admin opens notifications page → establish SSE connection
  2. Record admin connection in in-memory store (or cache: admin_id → SSE connection)
  3. When notification created: push to all active admin connections
  4. Heartbeat every 30 sec (Railway keepalive): `: heartbeat\n\n`
  5. Front-end auto-reconnect on disconnect
- NOTIFICATION CREATION:
  1. Service layer creates admin_notification record
  2. Publish to in-memory queue for SSE broadcast
  3. All connected admins receive update (page refresh not needed)
- NEW/UNHANDLED TAB:
  1. Show notifications with status=unhandled, sorted by created_at DESC
  2. Badge count on tab = count of requires_action=true AND status=unhandled
- BULK COMPLETE:
  1. Accept array of notification IDs
  2. Update status=completed for all
  3. Return count

**Dependencies:**
- All modules that create notifications (orders, custom_requests, color, production)
- External: Celery Beat (shipment_overdue scan)
- External: FastAPI SSE / EventStream (broadcast)

**Potential Conflicts:**
- SSE connection tracking must handle network disconnects gracefully
- Notification creation from multiple services must be thread-safe
- Heartbeat timing must not interfere with actual message delivery

---

### Module 13: Content Management

**Files to Create:**
- `content/router.py` - Public and admin endpoints for pages, settings, cases
- `content/service.py` - Page/setting/case management logic
- `content/models.py` - StaticPage, SystemSettings, CustomCase, CaseCategory ORM models
- `content/schemas/request.py` - UpdatePageRequest, UpdateSettingsRequest, CreateCaseRequest
- `content/schemas/response.py` - PageResponse, SystemSettingsResponse, CaseResponse

**DB Tables Involved:**
- `static_pages` (id, slug, title, content, updated_at)
- `system_settings` (key, value, updated_at)
- `custom_cases` (id, image_url, title, description, category_id, canvas_w_cm, canvas_h_cm, difficulty, is_published, created_at)
- `case_categories` (id, name, created_at)
- `custom_photo_prices` (id, canvas_w, canvas_h, difficulty, price)
- `custom_photo_surcharges` (id, category, label, amount, is_active, created_at)

**API Endpoints Covered:**
- GET /pages/{slug} (public, read page content)
- GET /admin/pages (admin list)
- PUT /admin/pages/{slug} (admin update)
- GET /system-settings/public (public, read front-end-needed settings)
- GET /admin/system-settings (admin list all)
- PATCH /admin/system-settings (admin update individual setting)
- GET /custom-cases (public list with pagination, category filter)
- GET /custom-cases/{id} (public detail)
- POST /admin/custom-cases (admin create)
- PUT /admin/custom-cases/{id} (admin update)
- DELETE /admin/custom-cases/{id} (admin delete)
- PATCH /admin/custom-cases/{id}/toggle-publish (admin toggle is_published)
- GET /admin/case-categories (admin list)
- POST /admin/case-categories (admin create)
- PUT /admin/case-categories/{id} (admin update)
- DELETE /admin/case-categories/{id} (admin delete, ON DELETE SET NULL for cases)
- GET /admin/custom-photo-prices (admin list)
- PUT /admin/custom-photo-prices/{id} (admin update price)
- GET /admin/custom-photo-surcharges (admin list)
- POST /admin/custom-photo-surcharges (admin create)
- PUT /admin/custom-photo-surcharges/{id} (admin update)
- PATCH /admin/custom-photo-surcharges/{id}/toggle-active (admin toggle is_active)
- DELETE /admin/custom-photo-surcharges/{id} (admin delete)

**Key Business Logic:**
- STATIC PAGES:
  1. Predefined slugs: size_guide, shipping, custom_process, pricing_reference, refund_policy
  2. Content stored as Markdown (rendered on front-end)
  3. On-demand creation (lazy): endpoint returns 404 if not yet created; admin can create via PUT
- SYSTEM SETTINGS:
  1. Key-value store for all global configuration
  2. Public settings: subset returned via /system-settings/public (for front-end)
  3. Keys: bank_account_number, bank_name, bank_account_name, quote_reply_days, product_info_*, paint_ml_per_cm2, paint_min_ml, paint_buffer_ratio
  4. Atomic updates: UPSERT semantics
- CUSTOM CASES:
  1. Showcases of completed custom work
  2. is_published flag controls visibility (soft publish, not hard delete)
  3. Category is optional (ON DELETE SET NULL when category deleted)
  4. Difficulty and canvas_w/h are optional (for portfolio items without strict sizing)
- CASE CATEGORIES:
  1. User-defined categories (人像, 寵物, etc.)
  2. Cascade delete product_tags; cascade SET NULL on custom_cases.category_id
- CUSTOM PHOTO PRICING:
  1. Matrix: canvas_w × canvas_h × difficulty → base_price
  2. UNIQUE constraint on (canvas_w, canvas_h, difficulty)
  3. Used in quotation base price lookup
- CUSTOM PHOTO SURCHARGES:
  1. Dynamic add-on fees for custom photos
  2. Category groups them (人物數量, 照片類型, 複雜度)
  3. is_active controls display in quotation UI
  4. Admin can add/remove/toggle without code changes

**Dependencies:**
- None (isolated content layer)

**Potential Conflicts:**
- System settings changes must be immediately visible to all services (consider caching invalidation)
- Case deletion should soft-delete (set is_published=false) instead of hard delete for history

---

### Module 14: Upload

**Files to Create:**
- `upload/router.py` - Upload endpoints for presigned URLs
- `upload/service.py` - Firebase presigned URL generation
- `upload/schemas/request.py` - GetUploadUrlRequest
- `upload/schemas/response.py` - UploadUrlResponse

**DB Tables Involved:**
- None (Firebase coordinates file storage; metadata stored elsewhere)

**API Endpoints Covered:**
- POST /upload/product-image (admin, get presigned URL for product images)
- POST /upload/custom-photo (customer, get presigned URL for custom photos)
- POST /upload/case-image (admin, get presigned URL for case showcase images)
- POST /upload/production-image (admin, get presigned URL for production files)

**Key Business Logic:**
- PRESIGNED URL GENERATION:
  1. Admin/customer requests presigned URL for file upload to Firebase Storage
  2. Back-end uses Firebase Admin SDK to generate a presigned PUT URL
  3. Return URL + public URL (or private path for later signing)
  4. Front-end uploads directly to Firebase (bypasses backend)
  5. Front-end sends back the URL to backend (e.g., POST /admin/products, POST /custom-requests)
  6. Backend validates URL format (matches expected bucket path) and stores reference
- BUCKET ORGANIZATION:
  1. product-images/{product_id}/{filename}
  2. custom-photos/{user_id}/{request_id}/{filename}
  3. case-images/{case_id}/{filename}
  4. production/{job_id}/{type}/{filename} (svg, filled_template, snapped_rgb)
- PUBLIC vs PRIVATE:
  1. Product images: public
  2. Custom photos: private (Firebase rules; signed URLs for access)
  3. Case images: public
  4. Production files (svg, snapped_rgb): private; filled_template public
- ERROR HANDLING:
  1. If Firebase credentials missing: return 503
  2. If file size exceeds limit (10MB for custom photos): front-end validation + backend reject on URL

**Dependencies:**
- External: Firebase Storage (file hosting)
- External: Firebase Admin SDK (presigned URL generation)

**Potential Conflicts:**
- URL validation must prevent path traversal or injection
- Presigned URL expiration must be sufficient for user upload (15-30 min typical)

---

### Module 15: Webhooks (ECpay)

**Files to Create:**
- `webhooks/router.py` - ECpay webhook endpoint
- `webhooks/service.py` - ECpay callback processing
- `webhooks/schemas/request.py` - ECpayWebhookRequest (generic dict, schema varies)
- `webhooks/schemas/response.py` - WebhookResponse (1|0 status)

**DB Tables Involved:**
- `shipments` (update status, delivered_at, ecpay_logistics_id)
- `orders` (update status to completed if all shipments delivered)
- `admin_notifications` (create ecpay_status notifications)

**API Endpoints Covered:**
- POST /webhooks/ecpay (public, process ECpay logistics callbacks)

**Key Business Logic:**
- WEBHOOK AUTHENTICATION:
  1. ECpay sends request with CheckMacValue
  2. Backend verifies CheckMacValue using ECpay keys (HMAC-SHA256)
  3. If verification fails: return 400, do not process
  4. If verification passes: process callback
- STATUS UPDATES:
  1. Receive shipment status update from ECpay (API logistics status)
  2. Find corresponding shipment by ecpay_logistics_id (or tracking_number)
  3. Map ECpay status to shipment.status:
     - 已取貨 / 已投遞 → delivered, delivered_at=now()
     - Other intermediate states (派送中, etc.) → create admin_notification only
  4. If shipment.status=delivered and all shipments in order are delivered:
     - order.status = completed
     - Send completion email to customer
     - Trigger reward coupon issuance (if applicable)
  5. If other state: create admin_notification (type=ecpay_status, requires_action=false)
- IDEMPOTENCY:
  1. ECpay may retry if no response (treat duplicate calls safely)
  2. Check if shipment.status already set; if yes, skip update
  3. Return 200 OK even if already processed
- RESPONSE FORMAT:
  1. Success: respond with `1` (ECpay convention)
  2. Failure: respond with `0`

**Dependencies:**
- Orders module (to update order status)
- Notifications module (for admin notification and customer email)
- External: ECpay API documentation (webhook format)

**Potential Conflicts:**
- Webhook processing must be idempotent
- Delayed webhooks must not overwrite newer status updates
- Concurrent webhook processing must not corrupt order state (use SELECT FOR UPDATE)

---

### Module 16: Sales Reports

**Files to Create:**
- `reports/router.py` - Admin sales report endpoints
- `reports/service.py` - Report aggregation queries
- `reports/models.py` - None (uses existing order models)
- `reports/schemas/request.py` - DateRangeRequest
- `reports/schemas/response.py` - SalesReportResponse

**DB Tables Involved:**
- `orders` (query completed orders, calculate revenue)

**API Endpoints Covered:**
- GET /admin/reports/sales (query with date_from, date_to)

**Key Business Logic:**
- REVENUE CALCULATION:
  1. Query orders where status=completed AND refund_amount is null or 0
  2. Sum order.total
  3. For partial refunds: sum (order.total - order.refund_amount)
  4. Filter by created_at within date range
- INITIAL METRICS:
  1. Period (from, to)
  2. Total orders (count)
  3. Total revenue (sum)
  4. Note explaining calculation (completed + unrefunded)
- FUTURE EXTENSIONS (noted but not implemented):
  1. Sales by product (variant breakdown)
  2. Discount usage statistics
  3. Refund rate analysis
  4. Monthly trend breakdown

**Dependencies:**
- Orders module (for order data)

**Potential Conflicts:**
- Report queries must not lock order tables for long (use read-only queries)
- Date range queries must use indexes on orders.created_at

---