"""
PRCE SEO Agent - prce.co.il
בדיקות SEO ייעודיות: title, description, H1, canonical, OG, noindex, alt text, RTL, favicon.
"""
import asyncio
import sys
import base64
import requests
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL   = 'https://prce.co.il'
WP_API     = f'{BASE_URL}/wp-json/wp/v2'
WP_USER    = 'ravidzeberger@gmail.com'
WP_PASS    = 'wa1d PY9e r5AQ IsBQ z9yN 29PK'
WP_AUTH    = base64.b64encode(f'{WP_USER}:{WP_PASS}'.encode()).decode()
WP_HEADERS = {'Authorization': f'Basic {WP_AUTH}'}

NOINDEX_EXPECTED = {'/thank-you/'}
SEO_EXEMPT_PAGES = {'/thank-you/'}


def get_all_wp_pages():
    pages = []
    for post_type in ['pages', 'posts']:
        page_num = 1
        while True:
            r = requests.get(f'{WP_API}/{post_type}',
                             headers=WP_HEADERS,
                             params={'per_page': 100, 'page': page_num, 'status': 'publish'},
                             timeout=15)
            if r.status_code != 200:
                break
            batch = r.json()
            if not batch:
                break
            for p in batch:
                link = p.get('link', '')
                path = link.replace(BASE_URL, '').rstrip('/') + '/'
                if path == '//':
                    path = '/'
                pages.append({'path': path, 'name': p.get('title', {}).get('rendered', path)})
            if len(batch) < 100:
                break
            page_num += 1
    if not any(p['path'] == '/' for p in pages):
        pages.insert(0, {'path': '/', 'name': 'דף הבית'})
    return pages


async def check_seo(page, page_info):
    url    = BASE_URL + page_info['path']
    issues = []

    try:
        resp = await page.goto(url, wait_until='load', timeout=60_000)
        if resp and resp.status != 200:
            return {'path': page_info['path'], 'name': page_info['name'], 'issues': [
                {'severity': 'error', 'check': 'טעינת עמוד', 'detail': f'HTTP {resp.status}'}
            ]}
    except Exception as e:
        return {'path': page_info['path'], 'name': page_info['name'], 'issues': [
            {'severity': 'error', 'check': 'טעינת עמוד', 'detail': str(e)[:80]}
        ]}

    await page.wait_for_timeout(2_000)

    # Meta Title
    title = (await page.evaluate("() => document.title || ''")).strip()
    if not title:
        issues.append({'severity': 'error', 'check': 'כותרת (title)',
                       'detail': 'חסרה לחלוטין',
                       'fix': 'הוסף Title ב-Yoast SEO → עריכת עמוד → SEO → כותרת SEO'})
    elif len(title) < 20:
        issues.append({'severity': 'warning', 'check': 'כותרת (title)',
                       'detail': f'קצרה מדי: {len(title)} תווים (מינימום 30)',
                       'fix': 'הרחב את הכותרת ב-Yoast SEO'})
    elif len(title) > 65:
        issues.append({'severity': 'warning', 'check': 'כותרת (title)',
                       'detail': f'ארוכה מדי: {len(title)} תווים (מקסימום 60)',
                       'fix': 'קצר את הכותרת — גוגל יחתוך אחרי 60 תווים'})

    # Meta Description
    desc = await page.evaluate(
        "() => document.querySelector('meta[name=\"description\"]')?.content?.trim() || ''")
    if not desc and page_info['path'] not in SEO_EXEMPT_PAGES:
        issues.append({'severity': 'error', 'check': 'תיאור (description)',
                       'detail': 'חסר',
                       'fix': 'הוסף תיאור ב-Yoast SEO → עריכת עמוד → SEO → מטא תיאור'})
    elif desc and len(desc) < 80:
        issues.append({'severity': 'warning', 'check': 'תיאור (description)',
                       'detail': f'קצר מדי: {len(desc)} תווים (מינימום 120)',
                       'fix': 'הרחב את התיאור'})
    elif desc and len(desc) > 165:
        issues.append({'severity': 'warning', 'check': 'תיאור (description)',
                       'detail': f'ארוך מדי: {len(desc)} תווים (מקסימום 160)',
                       'fix': 'קצר את התיאור'})

    # H1
    h1_count = await page.evaluate("() => document.querySelectorAll('h1').length")
    if h1_count == 0:
        issues.append({'severity': 'error', 'check': 'H1',
                       'detail': 'אין H1 בעמוד',
                       'fix': 'הוסף כותרת H1 ב-Elementor'})
    elif h1_count > 1:
        issues.append({'severity': 'warning', 'check': 'H1',
                       'detail': f'יש {h1_count} תגיות H1 (צריך בדיוק אחת)',
                       'fix': 'השאר H1 יחיד, שאר הכותרות יהיו H2/H3'})

    # Canonical
    canonical = await page.evaluate(
        "() => document.querySelector('link[rel=\"canonical\"]')?.href || ''")
    if not canonical and page_info['path'] not in SEO_EXEMPT_PAGES:
        issues.append({'severity': 'warning', 'check': 'Canonical URL',
                       'detail': 'חסר',
                       'fix': 'הפעל Yoast SEO — הוא מוסיף canonical אוטומטית'})

    # Open Graph
    og_title = await page.evaluate(
        "() => document.querySelector('meta[property=\"og:title\"]')?.content || ''")
    og_image = await page.evaluate(
        "() => document.querySelector('meta[property=\"og:image\"]')?.content || ''")
    if not og_title:
        issues.append({'severity': 'warning', 'check': 'Open Graph',
                       'detail': 'og:title חסר',
                       'fix': 'הגדר ב-Yoast SEO → לשונית Social'})
    if not og_image:
        issues.append({'severity': 'warning', 'check': 'Open Graph',
                       'detail': 'og:image חסר',
                       'fix': 'הגדר תמונת שיתוף ב-Yoast SEO → לשונית Social → תמונת Facebook'})

    # Noindex
    noindex = await page.evaluate("""
        () => (document.querySelector('meta[name="robots"]')?.content || '').includes('noindex')
    """)
    if noindex and page_info['path'] not in NOINDEX_EXPECTED:
        issues.append({'severity': 'error', 'check': 'Noindex ⚠️ קריטי',
                       'detail': f'העמוד מסומן noindex — גוגל לא יאנדקס!',
                       'fix': 'Yoast SEO → עריכת עמוד → Advanced → Allow search engines to index'})

    # Alt Text
    imgs_no_alt = await page.evaluate("""
        () => Array.from(document.querySelectorAll('img'))
            .filter(img =>
                !img.closest('[aria-hidden="true"]') &&
                img.getAttribute('role') !== 'presentation' &&
                !(img.src||'').includes('data:') &&
                !img.getAttribute('alt') && img.getAttribute('alt') !== '')
            .map(img => (img.src||'').split('/').pop().split('?')[0])
            .filter((v,i,a) => v && a.indexOf(v)===i).slice(0,5)
    """)
    if imgs_no_alt:
        issues.append({'severity': 'warning', 'check': 'Alt Text',
                       'detail': f'חסר בתמונות: {", ".join(imgs_no_alt)}',
                       'fix': 'הוסף alt text ב-WordPress → מדיה'})

    # RTL
    rtl_ok = await page.evaluate("""
        () => {
            const dir = document.documentElement.getAttribute('dir') ||
                        document.body.getAttribute('dir') ||
                        getComputedStyle(document.body).direction;
            return dir === 'rtl';
        }
    """)
    if not rtl_ok:
        issues.append({'severity': 'warning', 'check': 'RTL',
                       'detail': 'כיוון האתר לא מוגדר RTL',
                       'fix': 'WordPress → הגדרות → כללי → שפה: עברית'})

    # Favicon
    fav_url = await page.evaluate("""
        () => document.querySelector(
            'link[rel="icon"],link[rel="shortcut icon"],link[rel="apple-touch-icon"]'
        )?.href || null
    """)
    if not fav_url:
        issues.append({'severity': 'warning', 'check': 'Favicon',
                       'detail': 'חסר',
                       'fix': 'WordPress → מראה → התאמה אישית → זהות האתר → סמל האתר'})
    else:
        try:
            fr = requests.head(fav_url, timeout=5, allow_redirects=True)
            if fr.status_code != 200:
                issues.append({'severity': 'warning', 'check': 'Favicon',
                               'detail': f'HTTP {fr.status_code}',
                               'fix': 'העלה מחדש דרך מראה → התאמה אישית → סמל האתר'})
        except Exception:
            pass

    return {'path': page_info['path'], 'name': page_info['name'], 'issues': issues}


def send_whatsapp(message: str) -> bool:
    try:
        from twilio.rest import Client
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        import config as cfg
        client = Client(cfg.TWILIO_ACCOUNT_SID, cfg.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=cfg.TWILIO_FROM_NUMBER,
            to=f"whatsapp:+{cfg.WHATSAPP_PHONE}",
            body=message
        )
        print(f"✅ WhatsApp נשלח: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ WhatsApp error: {e}")
        return False


def build_seo_summary(results):
    today = datetime.now().strftime('%d/%m/%Y')
    RTL   = '\u200F'
    lines = [
        "🔍 *SEO יומי — prce.co.il*",
        f"📅 {today}",
        "",
    ]

    errors   = []
    warnings = []
    for r in results:
        for issue in r['issues']:
            entry = f"• {r['path']}: {issue['check']} — {issue['detail']}"
            if issue['severity'] == 'error':
                errors.append(entry)
            else:
                warnings.append(entry)

    if not errors and not warnings:
        lines.append("✅ *כל בדיקות ה-SEO תקינות!*")
    else:
        if errors:
            lines.append(f"❌ *שגיאות ({len(errors)}):*")
            for e in errors[:8]:
                lines.append(f"  {e}")
            if len(errors) > 8:
                lines.append(f"  ...ועוד {len(errors)-8}")
            lines.append("")
        if warnings:
            lines.append(f"⚠️ *אזהרות ({len(warnings)}):*")
            for w in warnings[:6]:
                lines.append(f"  {w}")
            if len(warnings) > 6:
                lines.append(f"  ...ועוד {len(warnings)-6}")

    lines.append("\n— SEO Agent • prce.co.il")
    return '\n'.join(RTL + l if l.strip() else l for l in lines)


async def run_seo():
    print(f"\n{'='*55}")
    print(f"  PRCE SEO Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    pages = get_all_wp_pages()
    print(f"נמצאו {len(pages)} עמודים\n")

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='he-IL'
        )
        page = await context.new_page()

        for page_info in pages:
            result = await check_seo(page, page_info)
            results.append(result)
            errs  = [i for i in result['issues'] if i['severity'] == 'error']
            warns = [i for i in result['issues'] if i['severity'] == 'warning']
            icon  = '[ERROR]' if errs else ('[WARN] ' if warns else '[OK]   ')
            print(f"{icon}  {page_info['name']} ({page_info['path']})")

        await browser.close()

    total_errors   = sum(len([i for i in r['issues'] if i['severity']=='error'])   for r in results)
    total_warnings = sum(len([i for i in r['issues'] if i['severity']=='warning']) for r in results)
    print(f"\nסיכום: {total_errors} שגיאות | {total_warnings} אזהרות")

    print("\nשולח WhatsApp SEO...")
    send_whatsapp(build_seo_summary(results))


if __name__ == '__main__':
    asyncio.run(run_seo())
