import Link from "next/link";
export default function NotFound() { return <div className="not-found container"><span className="notfound-number">404</span><h1>Page not found / الصفحة غير موجودة</h1><p>The address may have changed. / ربما تغيّر عنوان الصفحة.</p><div><Link href="/en">English home</Link><Link href="/ar">الرئيسية العربية</Link></div></div>; }
