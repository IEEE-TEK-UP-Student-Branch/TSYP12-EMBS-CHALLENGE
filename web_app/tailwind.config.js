/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: '#212124',
          lighter: '#2a2a2d',
          darker: '#1a1a1c',
        },
        highlight: {
          DEFAULT: '#c5c5e9',
          light: '#d1d1ef',
          dark: '#b9b9e3',
        },
        accent: {
          DEFAULT: '#a8d5ba',
          light: '#b4dbc4',
          dark: '#9ccfb0',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
