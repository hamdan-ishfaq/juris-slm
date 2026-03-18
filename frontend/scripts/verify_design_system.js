#!/usr/bin/env node
/**
 * Design System Verification Script
 * 
 * Checks:
 * 1. Tailwind config has custom colors
 * 2. Core UI components exist
 * 3. No hardcoded px values in main pages
 * 4. Design system files exist
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

const log = {
  success: (msg) => console.log(`${colors.green}✓${colors.reset} ${msg}`),
  error: (msg) => console.log(`${colors.red}✗${colors.reset} ${msg}`),
  warn: (msg) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  info: (msg) => console.log(`${colors.cyan}ℹ${colors.reset} ${msg}`),
  title: (msg) => console.log(`\n${colors.blue}${msg}${colors.reset}`),
};

let passed = 0;
let failed = 0;
let warnings = 0;

// Check 1: Design system files exist
log.title('1. Checking Design System Files...');
const designSystemFiles = [
  'src/theme/colors.js',
  'src/theme/typography.js',
  'src/theme/spacing.js',
  'src/theme/index.js',
];

designSystemFiles.forEach((file) => {
  const filePath = path.join(projectRoot, file);
  if (fs.existsSync(filePath)) {
    log.success(`${file} exists`);
    passed++;
  } else {
    log.error(`${file} is missing`);
    failed++;
  }
});

// Check 2: Tailwind config has custom colors
log.title('2. Checking Tailwind Configuration...');
const tailwindConfigPath = path.join(projectRoot, 'tailwind.config.js');
if (fs.existsSync(tailwindConfigPath)) {
  const tailwindConfig = fs.readFileSync(tailwindConfigPath, 'utf8');
  
  if (tailwindConfig.includes('colors') && tailwindConfig.includes('extend')) {
    log.success('Tailwind config has custom color definitions');
    passed++;
  } else {
    log.error('Tailwind config is missing custom color definitions');
    failed++;
  }
  
  if (tailwindConfig.includes('import') && tailwindConfig.includes('./src/theme')) {
    log.success('Tailwind config imports design system');
    passed++;
  } else {
    log.error('Tailwind config does not import design system');
    failed++;
  }
} else {
  log.error('tailwind.config.js not found');
  failed++;
}

// Check 3: Core UI components exist
log.title('3. Checking Core UI Components...');
const coreComponents = [
  'src/components/ui/Button.jsx',
  'src/components/ui/Input.jsx',
  'src/components/ui/Card.jsx',
  'src/components/ui/Skeleton.jsx',
  'src/components/ui/index.js',
];

coreComponents.forEach((file) => {
  const filePath = path.join(projectRoot, file);
  if (fs.existsSync(filePath)) {
    log.success(`${file} exists`);
    passed++;
  } else {
    log.error(`${file} is missing`);
    failed++;
  }
});

// Check 4: Layout and Footer components exist
log.title('4. Checking Layout Components...');
const layoutComponents = [
  'src/components/Layout.jsx',
  'src/components/Footer.jsx',
];

layoutComponents.forEach((file) => {
  const filePath = path.join(projectRoot, file);
  if (fs.existsSync(filePath)) {
    log.success(`${file} exists`);
    passed++;
  } else {
    log.error(`${file} is missing`);
    failed++;
  }
});

// Check 5: No hardcoded px values in Login page
log.title('5. Checking for Magic Numbers...');
const loginPath = path.join(projectRoot, 'src/pages/Login.jsx');
if (fs.existsSync(loginPath)) {
  const loginContent = fs.readFileSync(loginPath, 'utf8');
  
  // Look for hardcoded px values (e.g., "32px", "width: 500px")
  const pxPattern = /(?:width|height|padding|margin|font-size|top|left|right|bottom):\s*\d+px/g;
  const matches = loginContent.match(pxPattern);
  
  if (!matches || matches.length === 0) {
    log.success('Login page uses Tailwind classes (no hardcoded px values)');
    passed++;
  } else {
    log.warn(`Login page has ${matches.length} hardcoded px values`);
    log.info(`Found: ${matches.slice(0, 3).join(', ')}...`);
    warnings++;
  }
  
  // Check if using design system components
  if (loginContent.includes('from \'../components/ui\'')) {
    log.success('Login page imports design system components');
    passed++;
  } else {
    log.warn('Login page does not import design system components');
    warnings++;
  }
} else {
  log.error('Login.jsx not found');
  failed++;
}

// Check 6: Footer has user contact info
log.title('6. Checking Footer Content...');
const footerPath = path.join(projectRoot, 'src/components/Footer.jsx');
if (fs.existsSync(footerPath)) {
  const footerContent = fs.readFileSync(footerPath, 'utf8');
  
  const requiredLinks = [
    { name: 'GitHub', pattern: /github\.com\/hamdan-ishfaq/i },
    { name: 'LinkedIn', pattern: /linkedin\.com\/in\/m-hamdan-ishfaq/i },
    { name: 'Email', pattern: /hamdanishfaq\.2005@gmail\.com/i },
  ];
  
  requiredLinks.forEach(({ name, pattern }) => {
    if (pattern.test(footerContent)) {
      log.success(`Footer contains ${name} link`);
      passed++;
    } else {
      log.error(`Footer is missing ${name} link`);
      failed++;
    }
  });
} else {
  log.error('Footer.jsx not found');
  failed++;
}

// Final Report
log.title('═══════════════════════════════════════');
log.title('  DESIGN SYSTEM VERIFICATION RESULTS');
log.title('═══════════════════════════════════════');
console.log(`\n  ${colors.green}Passed:${colors.reset}   ${passed}`);
console.log(`  ${colors.red}Failed:${colors.reset}   ${failed}`);
console.log(`  ${colors.yellow}Warnings:${colors.reset} ${warnings}\n`);

if (failed === 0) {
  log.success('All checks passed! Design system is properly configured.');
  process.exit(0);
} else {
  log.error(`${failed} check(s) failed. Please fix the issues above.`);
  process.exit(1);
}
