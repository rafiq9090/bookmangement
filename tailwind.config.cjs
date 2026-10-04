module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  safelist: ['bg-green-50', 'bg-orange-50', 'text-green-800', 'text-gray-800'],
  theme: {extend: {
    fontFamily: {sans: ['Inter', 'sans-serif'], heading: ['Poppins', 'sans-serif']},
    colors: {brand: {orange: '#FF5A1F', green: '#43A047', darkGreen: '#2E7D32', dark: '#111827', bgLight: '#FFFDF9'}}
  }},
  plugins: [require('@tailwindcss/forms')]
};
