import { Component } from "react";
import { useTranslation } from "react-i18next";

function CrashNotice()
{
	const { t } = useTranslation();

	return (
		<div className="flex min-h-full flex-col items-center justify-center gap-4 bg-brand-surface-alt p-8 text-center font-sans max-sm:p-4">
			<h1 className="m-0 text-brand-primary-darker">{t("crash.title")}</h1>
			<p>{t("crash.body")}</p>
			<button
				type="button"
				onClick={() => window.location.reload()}
				className="cursor-pointer rounded-lg border-none bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-hover"
			>
				{t("crash.reload")}
			</button>
		</div>
	);
}

class ErrorBoundary extends Component
{
	state = { failed: false };

	static getDerivedStateFromError()
	{
		return { failed: true };
	}

	render()
	{
		return this.state.failed ? <CrashNotice /> : this.props.children;
	}
}

export default ErrorBoundary;
