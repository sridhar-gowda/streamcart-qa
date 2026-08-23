# StreamCart — Product Scenario

## About StreamCart

**StreamCart** is a direct-to-consumer e-commerce platform that lets users
browse products, manage a shopping cart, and complete purchases. The product
is available on six platforms, each tailored to its device's interaction model.

---

## Platforms

### Web Application
- **Technology:** React single-page application (responsive)
- **Interaction:** Mouse/keyboard, standard browser navigation
- **Automation:** Selenium WebDriver or Playwright
- **Deployment:** CDN-hosted, accessed via Chrome, Firefox, Safari, Edge

### iOS Application
- **Technology:** Native Swift / SwiftUI
- **Interaction:** Touch (tap, swipe, pinch), gesture-based navigation
- **Automation:** Appium with XCUITest driver
- **Deployment:** App Store, TestFlight for internal builds

### Android Application
- **Technology:** Native Kotlin / Jetpack Compose
- **Interaction:** Touch (tap, swipe, long-press), back button navigation
- **Automation:** Appium with UiAutomator2 driver
- **Deployment:** Google Play, internal APK distribution

### Fire TV Application
- **Technology:** Native Android (Fire OS), remote-controlled UI
- **Interaction:** D-pad navigation (up, down, left, right, select, back) —
  **no touch, no mouse, no hover**
- **Automation:** Appium with UiAutomator2 driver
- **Deployment:** Amazon Appstore, sideloaded APK for testing
- **Key difference:** Focus-based navigation. Users move a visible focus
  indicator between elements. No concept of "click at coordinates."

### Roku Application
- **Technology:** BrightScript / SceneGraph
- **Interaction:** D-pad navigation (similar to Fire TV) — **no touch**
- **Automation:** Roku WebDriver (ECP-based, HTTP API) or Appium Roku driver
- **Deployment:** Roku Channel Store, sideloaded for testing
- **Key difference:** Completely different tech stack (not Android/iOS). Uses
  its own XML-based UI framework. Element identification differs from
  mobile/web.

### Apple TV Application
- **Technology:** Native tvOS / SwiftUI
- **Interaction:** Siri Remote (swipe-to-focus, click-to-select, menu button)
  — **no touch screen, gesture-based remote**
- **Automation:** Appium with XCUITest driver
- **Deployment:** App Store, TestFlight
- **Key difference:** Similar to iOS automation tooling but fundamentally
  different interaction model (remote control, not touch screen).

---

## Shared User Journey

Despite the platform differences, **all six platforms implement the same core
user journey:**

```
Login → Browse Products → Add to Cart → View Cart → Checkout → Confirmation
```

### Flow Details

1. **Login**
   - User enters credentials (username + password)
   - Valid credentials → redirected to product listing
   - Invalid credentials → error message displayed
   - Locked accounts → specific error message

2. **Browse Products (Inventory)**
   - Products displayed in a grid/list layout
   - Each product shows: name, description, price, image
   - Products can be sorted by name (A→Z, Z→A) and price (low→high, high→low)
   - User can add products to cart from this screen

3. **Add to Cart**
   - Adding a product updates a cart badge/indicator with the count
   - The same product can be removed (button toggles)
   - Cart state persists across navigation within the session

4. **View Cart**
   - Shows all added products with name and price
   - User can remove individual items
   - User can return to shopping ("continue shopping")
   - User can proceed to checkout

5. **Checkout**
   - **Step 1:** Enter shipping info (first name, last name, zip code)
     - All fields required — validation messages on missing fields
   - **Step 2:** Review order summary (items, item total, tax, grand total)
   - **Step 3:** Confirm order → success confirmation page

6. **Post-Purchase**
   - Confirmation message displayed
   - Option to return to product listing

---

## What Differs Across Platforms

| Aspect | Web | Mobile (iOS/Android) | TV (Fire TV/Roku/Apple TV) |
|--------|-----|---------------------|---------------------------|
| **Navigation** | URL-based, links, buttons | Screen transitions, back gesture/button | Focus-based, d-pad, remote |
| **Element interaction** | Click, type, hover | Tap, swipe, long-press | Navigate focus → select |
| **Locator strategy** | CSS selectors, data attributes, XPath | Accessibility IDs, XPath, resource IDs | Accessibility IDs, text, custom attributes |
| **Waits** | DOM readiness, AJAX completion | Screen load, animation completion | Focus settlement, screen rendering |
| **Unique actions** | Hover, right-click, drag-drop | Swipe, pinch-zoom, rotate | D-pad sequences, voice commands |
| **Viewport** | Variable (responsive) | Fixed per device | 1080p or 4K, 10-foot UI |
| **Input** | Keyboard (physical) | On-screen keyboard | On-screen keyboard via d-pad |

---

## For This Assessment

- **Implement fully:** Web platform tests using SauceDemo as the target
  application. SauceDemo's e-commerce flow maps directly to StreamCart's.
- **Design the abstraction:** Your framework should support adding any of the
  other five platforms by creating new driver adapters and platform-specific
  config — without modifying existing framework code.
- **Stub 2+ platforms:** Create skeleton implementations for at least two
  non-web platforms that demonstrate how your abstraction accommodates their
  unique interaction models.

You are NOT expected to have working Appium, Roku, or tvOS automation. The
stubs exist to prove your architecture can grow.
