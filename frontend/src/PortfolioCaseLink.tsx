import { Link, type LinkProps } from "react-router-dom";
import { Client, portfolioCase, publicPortfolio } from "./api";

export function PortfolioCaseLink({
  api,
  caseId,
  ...props
}: LinkProps & { api: Client; caseId: string }) {
  function prefetch() {
    if (publicPortfolio)
      void api.request(portfolioCase(caseId)).catch(() => undefined);
  }
  return <Link {...props} onMouseEnter={prefetch} onFocus={prefetch} />;
}
