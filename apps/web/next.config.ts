import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@jhc/core"],
  serverExternalPackages: ["pg"],
};

export default nextConfig;
