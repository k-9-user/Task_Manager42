import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const REFRESH_INTERVAL_MS = 15000;

function Status()
{
	const [health, setHealth] = useState(null);
	const [checkedAt, setCheckedAt] = useState(null);
	const [loading, setLoading] = useState(true);
	const { t } = useTranslation();

	useEffect(() =>
	{
		let cancelled = false;

		async function check()
		{
			try
			{
				const response = await fetch(`${import.meta.env.VITE_API_URL}/health`);
				const data = await response.json().catch(() => null);
				if (cancelled)
					return ;
				setHealth({ ok: response.ok, data });
			}
			catch
			{
				if (!cancelled)
					setHealth({ ok: false, data: null });
			}
			finally
			{
				if (!cancelled)
				{
					setCheckedAt(new Date());
					setLoading(false);
				}
			}
		}

		check();
		const interval = setInterval(check, REFRESH_INTERVAL_MS);
		return () => { cancelled = true; clearInterval(interval); };
	}, []);

	const operational = health?.ok && health?.data?.status === "ok" && health?.data?.db === "ok";

	return (
		<div className="flex min-h-full flex-col gap-6 bg-brand-surface-alt p-8 font-sans max-sm:p-4">
			<h1 className="m-0 text-[#2e1065]">{t("status.title")}</h1>

			{loading ? (
				<p>{t("loading.load")}</p>
			) : (
				<div className={`flex items-center gap-3 rounded-xl border p-5 ${operational ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
					<span className={`h-3 w-3 shrink-0 rounded-full ${operational ? "bg-green-500" : "bg-red-500"}`} />
					<div>
						<p className={`m-0 font-semibold ${operational ? "text-green-700" : "text-red-700"}`}>
							{operational ? t("status.operational") : t("status.degraded")}
						</p>
						{checkedAt && (
							<p className="m-0 text-xs text-gray-500">
								{t("status.lastChecked")} {checkedAt.toLocaleTimeString()}
							</p>
						)}
					</div>
				</div>
			)}

			<div className="rounded-xl border border-brand-surface-border bg-brand-surface p-5">
				<h2 className="mb-2 mt-0 text-base text-[#2e1065]">{t("status.componentsTitle")}</h2>
				<ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm text-[#4c1d95]">
					<li className="flex items-center justify-between rounded-lg bg-brand-surface-alt px-3 py-2">
						<span>API</span>
						<span className={health?.ok ? "text-green-600" : "text-red-600"}>
							{health?.ok ? t("status.up") : t("status.down")}
						</span>
					</li>
					<li className="flex items-center justify-between rounded-lg bg-brand-surface-alt px-3 py-2">
						<span>{t("status.database")}</span>
						<span className={health?.data?.db === "ok" ? "text-green-600" : "text-red-600"}>
							{health?.data?.db === "ok" ? t("status.up") : t("status.down")}
						</span>
					</li>
				</ul>
			</div>

			<div className="rounded-xl border border-brand-surface-border bg-brand-surface p-5 text-sm text-[#4c1d95]">
				<h2 className="mb-2 mt-0 text-base text-[#2e1065]">{t("status.backupTitle")}</h2>
				<p className="m-0">{t("status.backupBody")}</p>
			</div>
		</div>
	);
}

export default Status;
