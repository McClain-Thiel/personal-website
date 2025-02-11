/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath: process.env.NEXT_PUBLIC_BASE_PATH,
  images: {
    unoptimized: true,
  },
  // Skip OG route generation during static export
  experimental: {
    skipTrailingSlashRedirect: true,
  },
  distDir: 'out'
}

module.exports = nextConfig 