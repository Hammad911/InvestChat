/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: {
    serverActions: {
      bodySizeLimit: "200mb",
    },
  },
};

const { withSentryConfig } = require("@sentry/nextjs");

module.exports = withSentryConfig(nextConfig, {
  silent: true,
  org: "student-h5i",
  project: "javascript-nextjs",
  widenClientFileUpload: true,
  hideSourceMaps: true,
  disableLogger: true,
});
